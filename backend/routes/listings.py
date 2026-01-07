from datetime import datetime, timezone
from math import radians, cos, sin, asin, sqrt
from typing import List

from fastapi import APIRouter, Depends, Query, HTTPException

from ..firebase_client import get_current_user, get_db
from ..redis_client import cache_get, cache_set, cache_delete_pattern
from ..schemas import ListingCreate, Listing, ListingUpdate


router = APIRouter()


def haversine(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points on the earth (km).
    """
    # convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    r = 6371  # Radius of earth in kilometers
    return c * r


@router.post("/", response_model=Listing)
def create_listing(
    payload: ListingCreate,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    uid = current_user["uid"]
    doc_ref = db.collection("listings").document()
    now = datetime.now(timezone.utc)
    data = {
        **payload.model_dump(),
        "owner_uid": uid,
        "created_at": now.isoformat(),
        "status": "active",
    }
    doc_ref.set(data)
    
    # Invalidate listings cache when new listing is created
    cache_delete_pattern("listings:*")
    
    return Listing(id=doc_ref.id, created_at=now, owner_uid=uid, **payload.model_dump(), status="active")


@router.get("/", response_model=List[Listing])
def nearby_listings(
    lat: float = Query(...),
    lng: float = Query(...),
    radius_km: float = Query(3.0),
    db=Depends(get_db),
):
    """
    Fetch listings roughly within a radius (km) of a location.
    Cached for 2 minutes to reduce Firestore queries.
    NOTE: Firestore doesn't support geo-radius queries natively, so we:
      * read recent active listings
      * filter by haversine distance
    """
    # Create cache key based on location and radius
    cache_key = f"listings:lat_{lat:.4f}:lng_{lng:.4f}:radius_{radius_km}"
    
    # Try to get from cache
    cached = cache_get(cache_key)
    if cached:
        # Convert datetime strings back to datetime objects
        for item in cached:
            item["created_at"] = datetime.fromisoformat(item["created_at"])
        return [Listing(**item) for item in cached]
    
    # Cache miss - query Firestore
    docs = (
        db.collection("listings")
        .where("status", "==", "active")
        .stream()
    )
    out: List[Listing] = []
    for doc in docs:
        d = doc.to_dict()
        try:
            dist = haversine(lat, lng, d["lat"], d["lng"])
        except KeyError:
            continue
        if dist <= radius_km:
            created_at = datetime.fromisoformat(d["created_at"])
            out.append(
                Listing(
                    id=doc.id,
                    owner_uid=d["owner_uid"],
                    created_at=created_at,
                    status=d.get("status", "active"),
                    title=d["title"],
                    description=d["description"],
                    type=d["type"],
                    is_free=d.get("is_free", True),
                    is_trade=d.get("is_trade", False),
                    category=d.get("category"),
                    lat=d["lat"],
                    lng=d["lng"],
                )
            )
    # sort by created_at desc
    out.sort(key=lambda x: x.created_at, reverse=True)
    
    # Cache the results (convert datetime to string for JSON)
    cache_data = []
    for item in out:
        item_dict = item.model_dump()
        item_dict["created_at"] = item.created_at.isoformat()
        cache_data.append(item_dict)
    cache_set(cache_key, cache_data, expire_seconds=120)  # 2 minutes cache
    
    return out


@router.patch("/{listing_id}", response_model=Listing)
def update_listing(
    listing_id: str,
    payload: ListingUpdate,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """Update a listing (status, description, etc.). Only owner can update."""
    uid = current_user["uid"]
    ref = db.collection("listings").document(listing_id)
    doc = ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    d = doc.to_dict()
    if d["owner_uid"] != uid:
        raise HTTPException(status_code=403, detail="Only owner can update listing")
    
    update_data = {}
    if payload.status:
        update_data["status"] = payload.status
    if payload.description:
        update_data["description"] = payload.description
    
    if update_data:
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        ref.update(update_data)
        doc = ref.get()
        d = doc.to_dict()
        
        # Invalidate listings cache when listing is updated
        cache_delete_pattern("listings:*")
    
    created_at = datetime.fromisoformat(d["created_at"])
    return Listing(
        id=doc.id,
        owner_uid=d["owner_uid"],
        created_at=created_at,
        status=d.get("status", "active"),
        title=d["title"],
        description=d["description"],
        type=d["type"],
        is_free=d.get("is_free", True),
        is_trade=d.get("is_trade", False),
        category=d.get("category"),
        lat=d["lat"],
        lng=d["lng"],
    )

