## Neighbour Node – Local Sharing & Urgent Help

Full‑stack app where neighbours can list tools, skills, or surplus for free/trade, and broadcast urgent needs to nearby people.

Backend: Python (FastAPI) + Firebase Admin (Firestore).  
Frontend: React + Firebase Auth.  

### 1. Firebase Setup

1. Create a Firebase project in the Firebase console.
2. Enable **Authentication → Email/Password**.
3. Create a **Firestore** database in Native mode.
4. Create a **Web App** in Firebase and copy the config (apiKey, authDomain, etc.).
5. Create a **Service Account key**:
   - Settings → Service Accounts → “Generate new private key”.
   - Save the JSON file somewhere on your machine, e.g. `D:\secrets\firebase-service-account.json`.

### 2. Backend Configuration (Python / FastAPI)

From `D:\Projects\Neighbour_Node`:

1. **Install Redis (optional but recommended for caching):**
   - **Windows**: Download from https://redis.io/download or use WSL
   - **Docker**: `docker run -d -p 6379:6379 redis:latest`
   - **Note**: If Redis is not available, the app will work but without caching/rate limiting

2. Create/activate venv (already created as `venv`):

```bash
venv\Scripts\activate
```

3. Ensure dependencies:

```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project root:

```bash
GOOGLE_APPLICATION_CREDENTIALS=D:\secrets\firebase-service-account.json
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
```

5. Run the API:

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Check: `http://localhost:8000/health` should return `{"status": "ok"}`.

### 3. Frontend Configuration (React)

From `D:\Projects\Neighbour_Node\frontend`:

1. Create `.env` with your Firebase web config and API base:

```bash
REACT_APP_FIREBASE_API_KEY=your_api_key
REACT_APP_FIREBASE_AUTH_DOMAIN=your_project.firebaseapp.com
REACT_APP_FIREBASE_PROJECT_ID=your_project_id
REACT_APP_FIREBASE_STORAGE_BUCKET=your_project.appspot.com
REACT_APP_FIREBASE_MESSAGING_SENDER_ID=your_sender_id
REACT_APP_FIREBASE_APP_ID=your_app_id
REACT_APP_API_BASE=http://localhost:8000
```

2. Install node dependencies (already mostly installed but safe to run):

```bash
npm install
```

3. Start the dev server:

```bash
npm start
```

The app will be on `http://localhost:3000`.

### 4. How It Works (MVP)

- **Auth**: Frontend uses Firebase Email/Password auth. It passes the Firebase ID token to the Python API in the `Authorization: Bearer <token>` header.
- **Profiles**: `/auth/profile` (POST/GET) stores user profile + location in Firestore.
- **Listings**:
  - `POST /listings` – create an offer/request/skill tied to the user and their coordinates.
  - `GET /listings?lat=..&lng=..&radius_km=..` – returns nearby active listings using a simple Haversine filter.
- **Urgent Needs**:
  - `POST /urgent` – broadcast an urgent need (e.g., “Need jump starter now”) with a radius in km.
  - `GET /urgent/nearby?lat=..&lng=..&radius_km=..` – returns active urgent needs around you (auto‑expires after ~2 hours).
  - `POST /urgent/{id}/resolve` – mark your own urgent need as resolved.
  - `POST /urgent/{id}/messages` / `GET /urgent/{id}/messages` – simple messaging thread per urgent need, stored under a Firestore sub‑collection.

### 5. Frontend UI (MVP)

- **Login / Signup page** with email + password (using Firebase Auth).
- **Dashboard** (after login):
  - Left column:
    - Form to **create a listing** (title, description, type, free/trade).
    - List of **nearby listings**.
  - Right column:
    - Form to **broadcast an urgent need** (title, description, radius).
    - List of **urgent needs near you** (pulled from `GET /urgent/nearby`).

Location is taken from browser geolocation (with a simple fallback).

### 6. Features

- **Caching**: Redis caches listings (2 min), urgent needs (30 sec), and chatbot queries (1 min) to reduce Firestore queries
- **Rate Limiting**: 
  - General API: 100 requests/minute per IP
  - Listing creation: 10/minute per IP
  - Urgent needs: 5 per hour per user
- **Reactions**: Users can react to listings (like, helpful, available, unavailable)
- **Status Updates**: Listing owners can mark items as reserved or used up
- **Chatbot**: Search assistant that finds local listings and suggests delivery platforms
- **Respond with Listing**: Users can respond to urgent needs using their existing listings

### 7. Next Steps / Extensions

- Add a dedicated messaging UI (threads per listing and urgent need).
- Add push notifications (FCM) for urgent broadcasts and new messages.
- Add user ratings / trust, moderation.

