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


@router.get("/api/admin/vehicles", response_model=list[VehicleOut])
async def list_vehicles(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    vehicles = (
        await db.execute(select(Vehicle).order_by(Vehicle.name.asc(), Vehicle.plate.asc(), Vehicle.id.asc()))
    ).scalars().all()
    return [VehicleOut.model_validate(vehicle) for vehicle in vehicles]


@router.post("/api/admin/vehicles", response_model=VehicleOut, status_code=201)
async def create_vehicle(
    payload: VehicleCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    await _ensure_plate_available(db, payload.plate)
    vehicle = Vehicle(name=payload.name, plate=payload.plate)
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
    # SQLite n'applique pas ON DELETE SET NULL sans PRAGMA foreign_keys :
    # on vide explicitement les lignes de flotte qui utilisaient ce véhicule.
    await db.execute(
        update(FleetEntry).where(FleetEntry.vehicle_id == vehicle_id).values(vehicle_id=None)
    )
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
