from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from ..firebase_client import get_current_user, get_db
from ..schemas import ReactionCreate, Reaction


router = APIRouter()


@router.post("/listings/{listing_id}/reactions", response_model=Reaction)
def add_listing_reaction(
    listing_id: str,
    payload: ReactionCreate,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """Add or update a reaction to a listing."""
    uid = current_user["uid"]
    listing_ref = db.collection("listings").document(listing_id)
    if not listing_ref.get().exists:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    reactions_ref = listing_ref.collection("reactions")
    # Check if user already reacted
    existing = reactions_ref.where("user_uid", "==", uid).stream()
    existing_docs = list(existing)
    
    if existing_docs:
        # Update existing reaction
        doc_ref = existing_docs[0].reference
        doc_ref.update({
            "reaction_type": payload.reaction_type,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        doc_id = doc_ref.id
    else:
        # Create new reaction
        doc_ref = reactions_ref.document()
        now = datetime.now(timezone.utc)
        doc_ref.set({
            "user_uid": uid,
            "reaction_type": payload.reaction_type,
            "created_at": now.isoformat(),
        })
        doc_id = doc_ref.id
    
    doc = doc_ref.get()
    d = doc.to_dict()
    return Reaction(
        id=doc_id,
        user_uid=uid,
        reaction_type=payload.reaction_type,
        created_at=datetime.fromisoformat(d.get("created_at", d.get("updated_at"))),
    )


@router.get("/listings/{listing_id}/reactions", response_model=List[Reaction])
def get_listing_reactions(
    listing_id: str,
    db=Depends(get_db),
):
    """Get all reactions for a listing."""
    listing_ref = db.collection("listings").document(listing_id)
    if not listing_ref.get().exists:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    reactions = listing_ref.collection("reactions").stream()
    out = []
    for doc in reactions:
        d = doc.to_dict()
        out.append(Reaction(
            id=doc.id,
            user_uid=d["user_uid"],
            reaction_type=d["reaction_type"],
            created_at=datetime.fromisoformat(d.get("created_at", d.get("updated_at"))),
        ))
    return out


@router.post("/urgent/{urgent_id}/reactions", response_model=Reaction)
def add_urgent_reaction(
    urgent_id: str,
    payload: ReactionCreate,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """Add or update a reaction to an urgent need."""
    uid = current_user["uid"]
    urgent_ref = db.collection("urgent_needs").document(urgent_id)
    if not urgent_ref.get().exists:
        raise HTTPException(status_code=404, detail="Urgent need not found")
    
    reactions_ref = urgent_ref.collection("reactions")
    existing = reactions_ref.where("user_uid", "==", uid).stream()
    existing_docs = list(existing)
    
    if existing_docs:
        doc_ref = existing_docs[0].reference
        doc_ref.update({
            "reaction_type": payload.reaction_type,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        doc_id = doc_ref.id
    else:
        doc_ref = reactions_ref.document()
        now = datetime.now(timezone.utc)
        doc_ref.set({
            "user_uid": uid,
            "reaction_type": payload.reaction_type,
            "created_at": now.isoformat(),
        })
        doc_id = doc_ref.id
    
    doc = doc_ref.get()
    d = doc.to_dict()
    return Reaction(
        id=doc_id,
        user_uid=uid,
        reaction_type=payload.reaction_type,
        created_at=datetime.fromisoformat(d.get("created_at", d.get("updated_at"))),
    )


@router.get("/urgent/{urgent_id}/reactions", response_model=List[Reaction])
def get_urgent_reactions(
    urgent_id: str,
    db=Depends(get_db),
):
    """Get all reactions for an urgent need."""
    urgent_ref = db.collection("urgent_needs").document(urgent_id)
    if not urgent_ref.get().exists:
        raise HTTPException(status_code=404, detail="Urgent need not found")
    
    reactions = urgent_ref.collection("reactions").stream()
    out = []
    for doc in reactions:
        d = doc.to_dict()
        out.append(Reaction(
            id=doc.id,
            user_uid=d["user_uid"],
            reaction_type=d["reaction_type"],
            created_at=datetime.fromisoformat(d.get("created_at", d.get("updated_at"))),
        ))
    return out
