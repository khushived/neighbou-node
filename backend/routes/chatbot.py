import re
from typing import List
from math import radians, cos, sin, asin, sqrt

from fastapi import APIRouter, Depends, Query

from ..firebase_client import get_db
from ..redis_client import cache_get, cache_set
from ..schemas import ChatbotQuery, ChatbotResponse


router = APIRouter()


def haversine(lat1, lon1, lat2, lon2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return c * 6371


def search_listings(db, query: str, lat: float = None, lng: float = None, radius_km: float = 5.0):
    """Search listings by keywords."""
    query_lower = query.lower().strip()
    if not query_lower:
        return []
    
    # Extract keywords, filtering out common stop words
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'do', 'does', 'did', 'have', 'has', 'had', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'this', 'that', 'these', 'those'}
    keywords = [kw for kw in re.findall(r'\w+', query_lower) if kw not in stop_words and len(kw) > 2]
    
    # If no meaningful keywords, use the whole query as a phrase
    if not keywords:
        keywords = [query_lower]
    
    all_listings = db.collection("listings").where("status", "==", "active").stream()
    matches = []
    
    for doc in all_listings:
        d = doc.to_dict()
        title_lower = d.get("title", "").lower()
        desc_lower = d.get("description", "").lower()
        category_lower = (d.get("category") or "").lower()
        
        # Check if query phrase appears anywhere
        phrase_match = query_lower in title_lower or query_lower in desc_lower
        
        # Simple keyword matching
        score = 0
        if phrase_match:
            score += 10  # High score for phrase match
        
        for kw in keywords:
            if kw in title_lower:
                score += 3
            if kw in desc_lower:
                score += 2
            if kw in category_lower:
                score += 1
        
        if score > 0:
            item = {
                "id": doc.id,
                "title": d.get("title"),
                "description": d.get("description"),
                "type": d.get("type"),
                "is_free": d.get("is_free", True),
                "distance_km": None,
            }
            
            if lat and lng and "lat" in d and "lng" in d:
                item["distance_km"] = round(haversine(lat, lng, d["lat"], d["lng"]), 1)
                if item["distance_km"] > radius_km:
                    continue
            
            item["relevance_score"] = score
            matches.append(item)
    
    # Sort by relevance and distance
    matches.sort(key=lambda x: (x["relevance_score"], -(x["distance_km"] or 999)), reverse=True)
    return matches[:5]  # Top 5 matches


def generate_external_links(query: str):
    """Generate links to external platforms (Swiggy Instamart, Blinkit, etc.)."""
    query_encoded = query.replace(" ", "+")
    links = []
    
    # Swiggy Instamart
    links.append({
        "platform": "Swiggy Instamart",
        "url": f"https://www.swiggy.com/instamart/search?query={query_encoded}",
        "icon": "🛒",
    })
    
    # Blinkit
    links.append({
        "platform": "Blinkit",
        "url": f"https://blinkit.com/s/?q={query_encoded}",
        "icon": "⚡",
    })
    
    # BigBasket
    links.append({
        "platform": "BigBasket",
        "url": f"https://www.bigbasket.com/ps/?q={query_encoded}",
        "icon": "🛍️",
    })
    
    return links


@router.post("/query", response_model=ChatbotResponse)
def chatbot_query(
    payload: ChatbotQuery,
    db=Depends(get_db),
):
    """
    Chatbot that searches listings and provides suggestions.
    Can also suggest external platforms like Swiggy Instamart, Blinkit, etc.
    Results are cached for 1 minute.
    """
    query = payload.query.lower().strip()
    
    # Create cache key
    cache_key = f"chatbot:{query}"
    if payload.lat and payload.lng:
        cache_key += f":lat_{payload.lat:.4f}:lng_{payload.lng:.4f}"
    
    # Try cache
    cached = cache_get(cache_key)
    if cached:
        return ChatbotResponse(**cached)
    
    # Search local listings
    suggestions = []
    if payload.lat and payload.lng:
        suggestions = search_listings(db, payload.query, payload.lat, payload.lng, radius_km=5.0)
    else:
        suggestions = search_listings(db, payload.query)
    
    # Generate response
    response_parts = []
    
    if suggestions:
        response_parts.append(f"Found {len(suggestions)} nearby listing(s) matching '{payload.query}':")
        for i, item in enumerate(suggestions[:3], 1):
            dist_str = f" ({item['distance_km']} km away)" if item.get("distance_km") else ""
            free_str = " (Free)" if item.get("is_free") else ""
            response_parts.append(f"{i}. {item['title']}{dist_str}{free_str}")
    else:
        response_parts.append(f"No local listings found for '{payload.query}'.")
    
    # Always suggest external platforms
    external_links = generate_external_links(payload.query)
    response_parts.append("\nYou can also check these delivery platforms:")
    for link in external_links:
        response_parts.append(f"• {link['icon']} {link['platform']}")
    
    result = ChatbotResponse(
        response="\n".join(response_parts),
        suggestions=suggestions,
        external_links=external_links,
    )
    
    # Cache the result (1 minute)
    cache_set(cache_key, result.model_dump(), expire_seconds=60)
    
    return result


@router.get("/query", response_model=ChatbotResponse)
def chatbot_query_get(
    q: str = Query(..., description="Search query"),
    lat: float = Query(None),
    lng: float = Query(None),
    db=Depends(get_db),
):
    """GET endpoint for chatbot queries."""
    payload = ChatbotQuery(query=q, lat=lat, lng=lng)
    return chatbot_query(payload, db)
