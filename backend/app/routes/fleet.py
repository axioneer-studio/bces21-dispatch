"""Routes de la flotte (couche transport mince)."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers import fleet as cf
from app.deps import get_db, require_admin, require_page_access

router = APIRouter(tags=["fleet"])


# --- Lignes de la flotte ---


@router.post(
    "/api/dispatch/fleet",
    response_model=cf.FleetEntryOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_fleet_entry(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_page_access("dispatch")),
) -> cf.FleetEntryOut:
    return await cf.create_fleet_entry(db)


@router.patch(
    "/api/dispatch/fleet/{entry_id}", response_model=cf.FleetEntryOut
)
async def update_fleet_entry(
    entry_id: int,
    payload: cf.FleetEntryUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_page_access("dispatch")),
) -> cf.FleetEntryOut:
    return await cf.update_fleet_entry(entry_id, payload, db)


@router.delete(
    "/api/dispatch/fleet/{entry_id}", response_model=cf.MessageResponse
)
async def delete_fleet_entry(
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_page_access("dispatch")),
) -> cf.MessageResponse:
    return await cf.delete_fleet_entry(entry_id, db)


# --- Catalogue des véhicules ---


@router.get("/api/admin/vehicles", response_model=list[cf.VehicleOut])
async def list_vehicles(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_admin),
) -> list[cf.VehicleOut]:
    return await cf.list_vehicles(db)


@router.put(
    "/api/admin/vehicles/import", response_model=cf.VehicleImportResult
)
async def import_vehicles(
    payload: cf.VehicleImportRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_admin),
) -> cf.VehicleImportResult:
    return await cf.import_vehicles(payload, db)


@router.post(
    "/api/admin/vehicles", response_model=cf.VehicleOut, status_code=status.HTTP_201_CREATED
)
async def create_vehicle(
    payload: cf.VehicleCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_admin),
) -> cf.VehicleOut:
    return await cf.create_vehicle(payload, db)


@router.patch("/api/admin/vehicles/{vehicle_id}", response_model=cf.VehicleOut)
async def update_vehicle(
    vehicle_id: int,
    payload: cf.VehicleUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_admin),
) -> cf.VehicleOut:
    return await cf.update_vehicle(vehicle_id, payload, db)


@router.delete("/api/admin/vehicles/{vehicle_id}", response_model=cf.MessageResponse)
async def delete_vehicle(
    vehicle_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_admin),
) -> cf.MessageResponse:
    return await cf.delete_vehicle(vehicle_id, db)


# --- Emplacements de stationnement ---


@router.get("/api/admin/parking-spots", response_model=list[cf.ParkingSpotOut])
async def list_parking_spots(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_admin),
) -> list[cf.ParkingSpotOut]:
    return await cf.list_parking_spots(db)


@router.post(
    "/api/admin/parking-spots",
    response_model=cf.ParkingSpotOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_parking_spot(
    payload: cf.ParkingSpotRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_admin),
) -> cf.ParkingSpotOut:
    return await cf.create_parking_spot(payload, db)


@router.patch("/api/admin/parking-spots/{spot_id}", response_model=cf.ParkingSpotOut)
async def update_parking_spot(
    spot_id: int,
    payload: cf.ParkingSpotRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_admin),
) -> cf.ParkingSpotOut:
    return await cf.update_parking_spot(spot_id, payload, db)


@router.delete("/api/admin/parking-spots/{spot_id}", response_model=cf.MessageResponse)
async def delete_parking_spot(
    spot_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_admin),
) -> cf.MessageResponse:
    return await cf.delete_parking_spot(spot_id, db)
