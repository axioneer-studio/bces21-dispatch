"""Flotte de véhicules : lignes de l'encart Dispatch et catalogues d'Administration.

Chaque modification rediffuse le snapshot du Dispatch, qui contient les lignes
de la flotte ainsi que les listes de véhicules et d'emplacements.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from deps import require_admin, require_page_access
from dispatch import push_snapshot
from models import FleetEntry, ParkingSpot, User, Vehicle
from schemas import (
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

router = APIRouter(tags=["fleet"])


# --- Lignes de la flotte (tout compte ayant accès au Dispatch) ---

@router.post("/api/dispatch/fleet", response_model=FleetEntryOut, status_code=201)
async def create_fleet_entry(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("dispatch")),
):
    last_order = await db.scalar(select(func.max(FleetEntry.order)))
    entry = FleetEntry(order=(last_order + 1) if last_order is not None else 0)
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    await push_snapshot(db)
    return FleetEntryOut.model_validate(entry)


@router.patch("/api/dispatch/fleet/{entry_id}", response_model=FleetEntryOut)
async def update_fleet_entry(
    entry_id: int,
    payload: FleetEntryUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("dispatch")),
):
    entry = await db.get(FleetEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Ligne de flotte introuvable.")
    data = payload.model_dump(exclude_unset=True)

    vehicle_id = data.get("vehicle_id")
    if vehicle_id is not None:
        if await db.get(Vehicle, vehicle_id) is None:
            raise HTTPException(status_code=404, detail="Véhicule introuvable.")
        # Un véhicule ne figure que sur une seule ligne.
        used = await db.scalar(
            select(FleetEntry.id)
            .where(FleetEntry.vehicle_id == vehicle_id, FleetEntry.id != entry.id)
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


@router.delete("/api/dispatch/fleet/{entry_id}", response_model=MessageResponse)
async def delete_fleet_entry(
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("dispatch")),
):
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
    # Tri stable : l'ordre par plaque est conservé à modèle égal.
    return sorted(
        by_plate,
        key=lambda v: (v.model is not None, (v.model or "").casefold()),
        reverse=True,
    )


async def _clear_fleet_vehicles(db: AsyncSession, vehicle_ids: list[int]) -> None:
    # SQLite n'applique pas ON DELETE SET NULL sans PRAGMA foreign_keys :
    # on vide explicitement les lignes de flotte qui utilisaient ces véhicules.
    await db.execute(
        update(FleetEntry).where(FleetEntry.vehicle_id.in_(vehicle_ids)).values(vehicle_id=None)
    )


@router.get("/api/admin/vehicles", response_model=list[VehicleOut])
async def list_vehicles(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return [VehicleOut.model_validate(vehicle) for vehicle in await _all_vehicles(db)]


@router.put("/api/admin/vehicles/import", response_model=VehicleImportResult)
async def import_vehicles(
    payload: VehicleImportRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Remplace le catalogue par la liste importée.

    Un véhicule existant est reconnu à sa plaque (ou, sans plaque, à son nom) :
    il garde son identifiant, donc les lignes de flotte qui l'utilisent. Les
    véhicules absents de la liste sont supprimés.
    """
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


@router.post("/api/admin/vehicles", response_model=VehicleOut, status_code=201)
async def create_vehicle(
    payload: VehicleCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    await _ensure_plate_available(db, payload.plate)
    vehicle = Vehicle(name=payload.name, plate=payload.plate, model=payload.model)
    db.add(vehicle)
    await db.commit()
    await db.refresh(vehicle)
    await push_snapshot(db)
    return VehicleOut.model_validate(vehicle)


@router.patch("/api/admin/vehicles/{vehicle_id}", response_model=VehicleOut)
async def update_vehicle(
    vehicle_id: int,
    payload: VehicleUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
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


@router.delete("/api/admin/vehicles/{vehicle_id}", response_model=MessageResponse)
async def delete_vehicle(
    vehicle_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
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


@router.get("/api/admin/parking-spots", response_model=list[ParkingSpotOut])
async def list_parking_spots(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    spots = (
        await db.execute(select(ParkingSpot).order_by(ParkingSpot.name.asc()))
    ).scalars().all()
    return [ParkingSpotOut.model_validate(spot) for spot in spots]


@router.post("/api/admin/parking-spots", response_model=ParkingSpotOut, status_code=201)
async def create_parking_spot(
    payload: ParkingSpotRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    await _ensure_spot_name_available(db, payload.name)
    spot = ParkingSpot(name=payload.name)
    db.add(spot)
    await db.commit()
    await db.refresh(spot)
    await push_snapshot(db)
    return ParkingSpotOut.model_validate(spot)


@router.patch("/api/admin/parking-spots/{spot_id}", response_model=ParkingSpotOut)
async def update_parking_spot(
    spot_id: int,
    payload: ParkingSpotRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    spot = await db.get(ParkingSpot, spot_id)
    if spot is None:
        raise HTTPException(status_code=404, detail="Emplacement introuvable.")
    await _ensure_spot_name_available(db, payload.name, spot.id)
    spot.name = payload.name
    await db.commit()
    await db.refresh(spot)
    await push_snapshot(db)
    return ParkingSpotOut.model_validate(spot)


@router.delete("/api/admin/parking-spots/{spot_id}", response_model=MessageResponse)
async def delete_parking_spot(
    spot_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    spot = await db.get(ParkingSpot, spot_id)
    if spot is None:
        raise HTTPException(status_code=404, detail="Emplacement introuvable.")
    # Les lignes de flotte gardent leur texte : l'emplacement y est libre.
    await db.delete(spot)
    await db.commit()
    await push_snapshot(db)
    return MessageResponse(message="Emplacement supprimé.")
