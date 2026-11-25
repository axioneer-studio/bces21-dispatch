"""Contrôleur de la flotte : lignes de l'encart Dispatch + catalogue véhicules/emplacements."""

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.dispatch import push_snapshot
from app.models import FleetEntry, ParkingSpot, Vehicle
from app.schemas import (
    FleetEntryOut,
    FleetEntryUpdateRequest,
    MessageResponse,
    ParkingSpotOut,
    ParkingSpotRequest,
    VehicleCreateRequest,
    VehicleImportRequest,
    VehicleImportResult,
    VehicleOut,
    VehicleUpdateRequest,
)

# --- Lignes de la flotte (tout compte ayant accès au Dispatch) ---


async def create_fleet_entry(db: AsyncSession) -> FleetEntryOut:
    last_order = await db.scalar(select(func.max(FleetEntry.order)))
    entry = FleetEntry(order=(last_order + 1) if last_order is not None else 0)
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    await push_snapshot(db)
    return FleetEntryOut.model_validate(entry)


async def update_fleet_entry(
    entry_id: int, payload: FleetEntryUpdateRequest, db: AsyncSession
) -> FleetEntryOut:
    entry = await db.get(FleetEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Ligne de flotte introuvable.")
    data = payload.model_dump(exclude_unset=True)

    vehicle_id = data.get("vehicle_id")
    if vehicle_id is not None:
        if await db.get(Vehicle, vehicle_id) is None:
            raise HTTPException(status_code=404, detail="Véhicule introuvable.")
        used = await db.scalar(
            select(FleetEntry.id)
            .where(FleetEntry.vehicle_id == vehicle_id, FleetEntry.id != entry_id)
            .limit(1)
        )
        if used is not None:
            raise HTTPException(
                status_code=409, detail="Ce véhicule figure déjà dans la flotte."
            )

    for key, value in data.items():
        if key in {"location", "note"} and value is None:
            value = ""
        setattr(entry, key, value)
    await db.commit()
    await db.refresh(entry)
    await push_snapshot(db)
    return FleetEntryOut.model_validate(entry)


async def delete_fleet_entry(entry_id: int, db: AsyncSession) -> MessageResponse:
    entry = await db.get(FleetEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Ligne de flotte introuvable.")
    await db.delete(entry)
    await db.commit()
    await push_snapshot(db)
    return MessageResponse(message="Ligne supprimée.")


# --- Catalogue des véhicules (Administration) ---


async def _ensure_plate_available(
    db: AsyncSession, plate: str | None, vehicle_id: int | None = None
) -> None:
    if not plate:
        return
    filters = [func.upper(Vehicle.plate) == plate.upper()]
    if vehicle_id is not None:
        filters.append(Vehicle.id != vehicle_id)
    if await db.scalar(select(Vehicle.id).where(*filters).limit(1)) is not None:
        raise HTTPException(
            status_code=409, detail="Un véhicule porte déjà cette plaque."
        )


async def _all_vehicles(db: AsyncSession) -> list[Vehicle]:
    """Véhicules par modèle (Z → A) puis par plaque (A → Z) ; sans modèle ou sans plaque en dernier."""
    vehicles = (await db.execute(select(Vehicle))).scalars().all()
    by_plate = sorted(
        vehicles,
        key=lambda v: (v.plate is None, (v.plate or "").casefold(), v.name.casefold(), v.id),
    )
    return sorted(
        by_plate,
        key=lambda v: (v.model is not None, (v.model or "").casefold()),
        reverse=True,
    )


async def _clear_fleet_vehicles(db: AsyncSession, vehicle_ids: list[int]) -> None:
    await db.execute(
        update(FleetEntry).where(FleetEntry.vehicle_id.in_(vehicle_ids)).values(vehicle_id=None)
    )


async def list_vehicles(db: AsyncSession) -> list[VehicleOut]:
    return [VehicleOut.model_validate(vehicle) for vehicle in await _all_vehicles(db)]


async def import_vehicles(
    payload: VehicleImportRequest, db: AsyncSession
) -> VehicleImportResult:
    """Remplace le catalogue par la liste importée."""
    seen_plates: set[str] = set()
    for item in payload.vehicles:
        if item.plate is None:
            continue
        if item.plate in seen_plates:
            raise HTTPException(
                status_code=422, detail=f"La plaque {item.plate} apparaît plusieurs fois dans le fichier."
            )
        seen_plates.add(item.plate)

    existing = await _all_vehicles(db)
    by_plate = {vehicle.plate.upper(): vehicle for vehicle in existing if vehicle.plate}
    without_plate: dict[str, list[Vehicle]] = {}
    for vehicle in existing:
        if not vehicle.plate:
            without_plate.setdefault(vehicle.name, []).append(vehicle)

    kept_ids: set[int] = set()
    created = updated = 0
    for item in payload.vehicles:
        if item.plate is not None:
            vehicle = by_plate.get(item.plate)
        else:
            candidates = without_plate.get(item.name) or []
            vehicle = candidates.pop(0) if candidates else None
        if vehicle is None:
            db.add(Vehicle(name=item.name, plate=item.plate, model=item.model))
            created += 1
            continue
        kept_ids.add(vehicle.id)
        if (vehicle.name, vehicle.plate, vehicle.model) != (item.name, item.plate, item.model):
            vehicle.name = item.name
            vehicle.plate = item.plate
            vehicle.model = item.model
            updated += 1

    removed_ids = [vehicle.id for vehicle in existing if vehicle.id not in kept_ids]
    if removed_ids:
        await _clear_fleet_vehicles(db, removed_ids)
        for vehicle in existing:
            if vehicle.id in removed_ids:
                await db.delete(vehicle)

    await db.commit()
    await push_snapshot(db)
    return VehicleImportResult(
        created=created,
        updated=updated,
        deleted=len(removed_ids),
        vehicles=[VehicleOut.model_validate(vehicle) for vehicle in await _all_vehicles(db)],
    )


async def create_vehicle(
    payload: VehicleCreateRequest, db: AsyncSession
) -> VehicleOut:
    await _ensure_plate_available(db, payload.plate)
    vehicle = Vehicle(name=payload.name, plate=payload.plate, model=payload.model)
    db.add(vehicle)
    await db.commit()
    await db.refresh(vehicle)
    await push_snapshot(db)
    return VehicleOut.model_validate(vehicle)


async def update_vehicle(
    vehicle_id: int, payload: VehicleUpdateRequest, db: AsyncSession
) -> VehicleOut:
    vehicle = await db.get(Vehicle, vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Véhicule introuvable.")
    data = payload.model_dump(exclude_unset=True)
    if "plate" in data:
        await _ensure_plate_available(db, data["plate"], vehicle.id)
    for key, value in data.items():
        if key == "name" and value is None:
            continue
        setattr(vehicle, key, value)
    await db.commit()
    await db.refresh(vehicle)
    await push_snapshot(db)
    return VehicleOut.model_validate(vehicle)


async def delete_vehicle(vehicle_id: int, db: AsyncSession) -> MessageResponse:
    vehicle = await db.get(Vehicle, vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Véhicule introuvable.")
    await _clear_fleet_vehicles(db, [vehicle_id])
    await db.delete(vehicle)
    await db.commit()
    await push_snapshot(db)
    return MessageResponse(message="Véhicule supprimé.")


# --- Emplacements de stationnement (Administration) ---


async def _ensure_spot_name_available(
    db: AsyncSession, name: str, spot_id: int | None = None
) -> None:
    filters = [func.lower(ParkingSpot.name) == name.lower()]
    if spot_id is not None:
        filters.append(ParkingSpot.id != spot_id)
    if await db.scalar(select(ParkingSpot.id).where(*filters).limit(1)) is not None:
        raise HTTPException(status_code=409, detail="Cet emplacement existe déjà.")


async def list_parking_spots(db: AsyncSession) -> list[ParkingSpotOut]:
    spots = (
        await db.execute(select(ParkingSpot).order_by(ParkingSpot.name.asc()))
    ).scalars().all()
    return [ParkingSpotOut.model_validate(spot) for spot in spots]


async def create_parking_spot(
    payload: ParkingSpotRequest, db: AsyncSession
) -> ParkingSpotOut:
    await _ensure_spot_name_available(db, payload.name)
    spot = ParkingSpot(name=payload.name)
    db.add(spot)
    await db.commit()
    await db.refresh(spot)
    await push_snapshot(db)
    return ParkingSpotOut.model_validate(spot)


async def update_parking_spot(
    spot_id: int, payload: ParkingSpotRequest, db: AsyncSession
) -> ParkingSpotOut:
    spot = await db.get(ParkingSpot, spot_id)
    if spot is None:
        raise HTTPException(status_code=404, detail="Emplacement introuvable.")
    await _ensure_spot_name_available(db, payload.name, spot.id)
    spot.name = payload.name
    await db.commit()
    await db.refresh(spot)
    await push_snapshot(db)
    return ParkingSpotOut.model_validate(spot)


async def delete_parking_spot(spot_id: int, db: AsyncSession) -> MessageResponse:
    spot = await db.get(ParkingSpot, spot_id)
    if spot is None:
        raise HTTPException(status_code=404, detail="Emplacement introuvable.")
    await db.delete(spot)
    await db.commit()
    await push_snapshot(db)
    return MessageResponse(message="Emplacement supprimé.")
