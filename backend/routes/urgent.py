import re
from datetime import datetime, timezone, timedelta
from math import radians, cos, sin, asin, sqrt
from typing import List

from fastapi import APIRouter, Depends, Query, HTTPException

from ..firebase_client import get_current_user, get_db
from ..redis_client import cache_get, cache_set, cache_delete_pattern, rate_limit
from ..schemas import UrgentNeedCreate, UrgentNeed, Message, MessageCreate, RespondWithListingRequest


router = APIRouter()


def haversine(lat1, lon1, lat2, lon2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    r = 6371
    return c * r


@router.post("/", response_model=UrgentNeed)
def create_urgent_need(
    payload: UrgentNeedCreate,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    uid = current_user["uid"]
    
    # Rate limiting: max 5 urgent needs per user per hour
    rate_key = f"urgent_rate_limit:{uid}"
    if not rate_limit(rate_key, limit=5, window_seconds=3600):
        raise HTTPException(status_code=429, detail="Too many urgent needs. Please wait before creating another.")
    
    doc_ref = db.collection("urgent_needs").document()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=2)
    data = {
        **payload.model_dump(),
        "user_uid": uid,
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "status": "active",
    }
    doc_ref.set(data)
    
    # Invalidate urgent needs cache
    cache_delete_pattern("urgent_nearby:*")
    
    return UrgentNeed(
        id=doc_ref.id,
        user_uid=uid,
        created_at=now,
        status="active",
        **payload.model_dump(),
    )


@router.get("/nearby", response_model=List[UrgentNeed])
def nearby_urgent_needs(
    lat: float = Query(...),
    lng: float = Query(...),
    radius_km: float = Query(3.0),
    db=Depends(get_db),
):
    """
    Fetch active urgent needs around the given location.
    Cached for 30 seconds (urgent needs change frequently).
    """
    # Create cache key
    cache_key = f"urgent_nearby:lat_{lat:.4f}:lng_{lng:.4f}:radius_{radius_km}"
    
    # Try cache first
    cached = cache_get(cache_key)
    if cached:
        for item in cached:
            item["created_at"] = datetime.fromisoformat(item["created_at"])
        return [UrgentNeed(**item) for item in cached]
    
    # Cache miss - query Firestore
    now = datetime.now(timezone.utc)
    docs = (
        db.collection("urgent_needs")
        .where("status", "==", "active")
        .stream()
    )
    out: List[UrgentNeed] = []
    for doc in docs:
        d = doc.to_dict()
        try:
            dist = haversine(lat, lng, d["lat"], d["lng"])
        except KeyError:
            continue
        if dist <= radius_km:
            # expire old ones on the fly
            expires_at = datetime.fromisoformat(d["expires_at"])
            if expires_at < now:
                doc.reference.update({"status": "expired"})
                continue
            created_at = datetime.fromisoformat(d["created_at"])
            out.append(
                UrgentNeed(
                    id=doc.id,
                    user_uid=d["user_uid"],
                    created_at=created_at,
                    status=d.get("status", "active"),
                    title=d["title"],
                    description=d["description"],
                    lat=d["lat"],
                    lng=d["lng"],
                    radius_km=d.get("radius_km", 2.0),
                )
            )
    out.sort(key=lambda x: x.created_at, reverse=True)
    
    # Cache results (30 seconds for urgent needs)
    cache_data = []
    for item in out:
        item_dict = item.model_dump()
        item_dict["created_at"] = item.created_at.isoformat()
        cache_data.append(item_dict)
    cache_set(cache_key, cache_data, expire_seconds=30)
    
    return out


@router.post("/{urgent_id}/resolve")
def resolve_urgent_need(
    urgent_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Mark an urgent need as resolved (only by owner).
    """
    uid = current_user["uid"]
    ref = db.collection("urgent_needs").document(urgent_id)
    doc = ref.get()
    if not doc.exists:
        return {"status": "not_found"}
    d = doc.to_dict()
    if d["user_uid"] != uid:
        return {"status": "forbidden"}
    ref.update({"status": "resolved"})
    return {"status": "ok"}


@router.post("/{urgent_id}/messages", response_model=Message)
def post_urgent_message(
    urgent_id: str,
    payload: MessageCreate,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Post a message in response to an urgent need.
    """
    uid = current_user["uid"]
    urgent_ref = db.collection("urgent_needs").document(urgent_id)
    if not urgent_ref.get().exists:
        raise ValueError("Urgent need not found")
    messages_ref = urgent_ref.collection("messages").document()
    now = datetime.now(timezone.utc)
    data = {
        "sender_uid": uid,
        "content": payload.content,
        "created_at": now.isoformat(),
        "urgent_need_id": urgent_id,
    }
    messages_ref.set(data)
    return Message(
        id=messages_ref.id,
        conversation_id=urgent_id,
        sender_uid=uid,
        content=payload.content,
        created_at=now,
    )


@router.get("/{urgent_id}/messages", response_model=List[Message])
def list_urgent_messages(
    urgent_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    List messages for an urgent need (simple messaging history).
    """
    # ensure urgent need exists
    urgent_ref = db.collection("urgent_needs").document(urgent_id)
    if not urgent_ref.get().exists:
        raise ValueError("Urgent need not found")
    docs = (
        urgent_ref.collection("messages")
        .order_by("created_at")
        .stream()
    )
    out: List[Message] = []
    for doc in docs:
        d = doc.to_dict()
        created_at = datetime.fromisoformat(d["created_at"])
        out.append(
            Message(
                id=doc.id,
                conversation_id=urgent_id,
                sender_uid=d["sender_uid"],
                content=d["content"],
                created_at=created_at,
            )
        )
    return out


@router.get("/{urgent_id}/my-matching-listings")
def get_my_matching_listings(
    urgent_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Get the current user's listings that might match an urgent need.
    This helps users respond to urgent needs with their existing listings.
    """
    uid = current_user["uid"]
    urgent_ref = db.collection("urgent_needs").document(urgent_id)
    urgent_doc = urgent_ref.get()
    if not urgent_doc.exists:
        raise HTTPException(status_code=404, detail="Urgent need not found")
    
    urgent_data = urgent_doc.to_dict()
    urgent_title = urgent_data.get("title", "").lower()
    urgent_desc = urgent_data.get("description", "").lower()
    
    # Get user's active listings
    user_listings = (
        db.collection("listings")
        .where("owner_uid", "==", uid)
        .where("status", "==", "active")
        .stream()
    )
    
    matches = []
    urgent_keywords = set(re.findall(r'\w+', urgent_title + " " + urgent_desc))
    
    for doc in user_listings:
        d = doc.to_dict()
        listing_title = d.get("title", "").lower()
        listing_desc = d.get("description", "").lower()
        
        # Simple matching: check if any keywords overlap
        listing_keywords = set(re.findall(r'\w+', listing_title + " " + listing_desc))
        overlap = len(urgent_keywords & listing_keywords)
        
        if overlap > 0 or urgent_title in listing_title or urgent_desc in listing_desc:
            matches.append({
                "id": doc.id,
                "title": d.get("title"),
                "description": d.get("description"),
                "type": d.get("type"),
                "is_free": d.get("is_free", True),
                "match_score": overlap,
            })
    
    # Sort by match score
    matches.sort(key=lambda x: x["match_score"], reverse=True)
    return {"listings": matches}


@router.post("/{urgent_id}/respond-with-listing")
def respond_with_listing(
    urgent_id: str,
    payload: RespondWithListingRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Respond to an urgent need by linking one of your existing listings.
    This creates a message with a reference to the listing.
    """
    uid = current_user["uid"]
    
    # Verify urgent need exists
    urgent_ref = db.collection("urgent_needs").document(urgent_id)
    if not urgent_ref.get().exists:
        raise HTTPException(status_code=404, detail="Urgent need not found")
    
    # Verify listing exists and belongs to user
    listing_ref = db.collection("listings").document(payload.listing_id)
    listing_doc = listing_ref.get()
    if not listing_doc.exists:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    listing_data = listing_doc.to_dict()
    if listing_data.get("owner_uid") != uid:
        raise HTTPException(status_code=403, detail="You can only respond with your own listings")
    
    if listing_data.get("status") != "active":
        raise HTTPException(status_code=400, detail="Listing must be active")
    
    # Create a message linking to the listing
    messages_ref = urgent_ref.collection("messages").document()
    now = datetime.now(timezone.utc)
    listing_title = listing_data.get("title", "Unknown")
    message_content = f"I have this available: {listing_title}. Check my listing for details!"
    
    messages_ref.set({
        "sender_uid": uid,
        "content": message_content,
        "created_at": now.isoformat(),
        "urgent_need_id": urgent_id,
        "linked_listing_id": payload.listing_id,
    })
    
    return {
        "status": "ok",
        "message_id": messages_ref.id,
        "message": message_content,
    }

