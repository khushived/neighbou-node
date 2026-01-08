import os
import json
from functools import lru_cache

import firebase_admin
from dotenv import load_dotenv
from firebase_admin import auth as admin_auth, credentials, firestore
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


load_dotenv()


@lru_cache
def init_firebase_app():
    """
    Initialize Firebase Admin SDK.
    - For Render: use GOOGLE_APPLICATION_CREDENTIALS_JSON (JSON string)
    - For local: use GOOGLE_APPLICATION_CREDENTIALS (file path)
    """
    if not firebase_admin._apps:
        # Check for JSON string (deployment)
        cred_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        if cred_json:
            cred = credentials.Certificate(json.loads(cred_json))
        else:
            # Fall back to file path (local)
            cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if not cred_path:
                raise RuntimeError(
                    "Set GOOGLE_APPLICATION_CREDENTIALS_JSON or GOOGLE_APPLICATION_CREDENTIALS"
                )
            if not os.path.exists(cred_path):
                raise FileNotFoundError(f"Firebase file not found: {cred_path}")
            cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
    return firebase_admin.get_app()


security = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    """
    Verify Firebase ID token from Authorization: Bearer <token>.
    Returns the decoded token dict (with 'uid', 'email', etc.).
    """
    init_firebase_app()
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
        )

    token = creds.credentials
    try:
        decoded = admin_auth.verify_id_token(token)
        return decoded
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


def get_db():
    """
    Return a Firestore client.
    """
    init_firebase_app()
    return firestore.client()

