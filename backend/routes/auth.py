from fastapi import APIRouter, Depends

from ..firebase_client import get_current_user, get_db
from ..schemas import UserProfile


router = APIRouter()


@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    """
    Return the current Firebase user token info.
    """
    return current_user


@router.post("/profile")
def upsert_profile(
    profile: UserProfile,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Create or update the user's public profile in Firestore.
    """
    uid = current_user["uid"]
    doc_ref = db.collection("users").document(uid)
    doc_ref.set(profile.model_dump(), merge=True)
    return {"status": "ok"}


@router.get("/profile")
def get_profile(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    uid = current_user["uid"]
    doc = db.collection("users").document(uid).get()
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["uid"] = uid
    return data

