import React, { useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, Navigate } from 'react-router-dom';
import './App.css';
import { auth } from './firebase';
import { onAuthStateChanged, signInWithEmailAndPassword, createUserWithEmailAndPassword, signOut } from 'firebase/auth';
import { apiGet, apiPost } from './api';

function AuthGate({ children }) {
  const [user, setUser] = useState(undefined);

  useEffect(() => {
    const unsub = onAuthStateChanged(auth, (u) => setUser(u || null));
    return () => unsub();
  }, []);

  if (user === undefined) return <div className="center">Loading...</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function LoginPage() {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      if (isRegister) {
        await createUserWithEmailAndPassword(auth, email, password);
      } else {
        await signInWithEmailAndPassword(auth, email, password);
      }
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="center">
      <h1>Neighbour Node</h1>
      <form onSubmit={handleSubmit} className="card">
        <h2>{isRegister ? 'Create account' : 'Log in'}</h2>
        <input
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {error && <div className="error">{error}</div>}
        <button type="submit">{isRegister ? 'Sign up' : 'Sign in'}</button>
        <button
          type="button"
          className="link-btn"
          onClick={() => setIsRegister(!isRegister)}
        >
          {isRegister ? 'Already have an account? Log in' : "Don't have an account? Sign up"}
        </button>
      </form>
    </div>
  );
}

function Dashboard() {
  const [coords, setCoords] = useState(null);
  const [listings, setListings] = useState([]);
  const [urgent, setUrgent] = useState([]);
  const [reactions, setReactions] = useState({}); // { listing_id: { like: 0, helpful: 0, ... } }
  const [chatbotQuery, setChatbotQuery] = useState('');
  const [chatbotResponse, setChatbotResponse] = useState(null);
  const [showChatbot, setShowChatbot] = useState(false);
  const [matchingListings, setMatchingListings] = useState({}); // { urgent_id: [listings] }
  const [showRespondModal, setShowRespondModal] = useState(null); // urgent_id or null
  const [form, setForm] = useState({
    title: '',
    description: '',
    type: 'offer',
    is_free: true,
    is_trade: false,
    category: '',
  });
  const [urgentForm, setUrgentForm] = useState({
    title: '',
    description: '',
    radius_km: 2,
  });

  useEffect(() => {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const c = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        setCoords(c);
        refreshData(c);
      },
      () => {
        const fallback = { lat: 0, lng: 0 };
        setCoords(fallback);
        refreshData(fallback);
      }
    );
  }, []);

  const refreshData = async (c = coords) => {
    if (!c) return;
    try {
      const [nearListings, nearUrgent] = await Promise.all([
        apiGet(`/listings?lat=${c.lat}&lng=${c.lng}&radius_km=3`),
        apiGet(`/urgent/nearby?lat=${c.lat}&lng=${c.lng}&radius_km=3`),
      ]);
      setListings(nearListings);
      setUrgent(nearUrgent);
      
      // Load reactions for listings
      const reactionsMap = {};
      for (const listing of nearListings) {
        try {
          const listingReactions = await apiGet(`/reactions/listings/${listing.id}/reactions`);
          const counts = { like: 0, helpful: 0, available: 0, unavailable: 0 };
          listingReactions.forEach(r => {
            if (counts[r.reaction_type] !== undefined) {
              counts[r.reaction_type]++;
            }
          });
          reactionsMap[listing.id] = counts;
        } catch (e) {
          reactionsMap[listing.id] = { like: 0, helpful: 0, available: 0, unavailable: 0 };
        }
      }
      setReactions(reactionsMap);
    } catch (e) {
      console.error(e);
    }
  };

  const handleCreateListing = async (e) => {
    e.preventDefault();
    if (!coords) return;
    const payload = { ...form, lat: coords.lat, lng: coords.lng };
    await apiPost('/listings', payload);
    setForm({ ...form, title: '', description: '' });
    refreshData();
  };

  const handleCreateUrgent = async (e) => {
    e.preventDefault();
    if (!coords) return;
    const payload = { ...urgentForm, lat: coords.lat, lng: coords.lng };
    await apiPost('/urgent', payload);
    setUrgentForm({ ...urgentForm, title: '', description: '' });
    refreshData();
  };

  const handleLogout = async () => {
    await signOut(auth);
  };

  const handleReaction = async (type, listingId) => {
    try {
      await apiPost(`/reactions/listings/${listingId}/reactions`, { reaction_type: type });
      refreshData();
    } catch (e) {
      console.error(e);
    }
  };

  const handleUpdateStatus = async (listingId, newStatus) => {
    try {
      await apiPost(`/listings/${listingId}`, { status: newStatus }, 'PATCH');
      refreshData();
    } catch (e) {
      console.error(e);
    }
  };

  const handleChatbotQuery = async (e) => {
    e.preventDefault();
    if (!chatbotQuery.trim() || !coords) return;
    try {
      const response = await apiPost('/chatbot/query', {
        query: chatbotQuery,
        lat: coords.lat,
        lng: coords.lng,
      });
      setChatbotResponse(response);
    } catch (e) {
      console.error(e);
    }
  };

  const handleGetMatchingListings = async (urgentId) => {
    try {
      const response = await apiGet(`/urgent/${urgentId}/my-matching-listings`);
      setMatchingListings({ ...matchingListings, [urgentId]: response.listings });
      setShowRespondModal(urgentId);
    } catch (e) {
      console.error(e);
      alert('Could not load your listings. Make sure you have active listings.');
    }
  };

  const handleRespondWithListing = async (urgentId, listingId) => {
    try {
      await apiPost(`/urgent/${urgentId}/respond-with-listing`, { listing_id: listingId });
      setShowRespondModal(null);
      alert('Response sent! The requester will see your listing.');
    } catch (e) {
      console.error(e);
      alert('Failed to send response.');
    }
  };

  return (
    <div className="layout">
      <header className="topbar">
        <h1>Neighbour Node</h1>
        <div>
          <button onClick={() => setShowChatbot(!showChatbot)} className="chatbot-toggle">
            {showChatbot ? '❌ Close Chatbot' : '🤖 Ask Chatbot'}
          </button>
          <button onClick={handleLogout}>Log out</button>
        </div>
      </header>
      {showChatbot && (
        <div className="chatbot-panel">
          <h3>🤖 Search Assistant</h3>
          <p>Ask me to find items in nearby listings or check delivery platforms!</p>
          <form onSubmit={handleChatbotQuery} className="chatbot-form">
            <input
              placeholder="e.g., 'Do you have a drill?' or 'Where can I find tomatoes?'"
              value={chatbotQuery}
              onChange={(e) => setChatbotQuery(e.target.value)}
              className="chatbot-input"
            />
            <button type="submit">Search</button>
          </form>
          {chatbotResponse && (
            <div className="chatbot-response">
              <div className="chatbot-text">{chatbotResponse.response}</div>
              {chatbotResponse.suggestions && chatbotResponse.suggestions.length > 0 && (
                <div className="chatbot-suggestions">
                  <h4>Local Listings:</h4>
                  {chatbotResponse.suggestions.map((s, i) => (
                    <div key={i} className="suggestion-item">
                      <strong>{s.title}</strong> - {s.description}
                      {s.distance_km && <span> ({s.distance_km} km away)</span>}
                    </div>
                  ))}
                </div>
              )}
              {chatbotResponse.external_links && chatbotResponse.external_links.length > 0 && (
                <div className="chatbot-links">
                  <h4>Check Delivery Platforms:</h4>
                  {chatbotResponse.external_links.map((link, i) => (
                    <a
                      key={i}
                      href={link.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="external-link"
                    >
                      {link.icon} {link.platform}
                    </a>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
      <main className="main">
        <section className="column">
          <h2>Share something</h2>
          <form onSubmit={handleCreateListing} className="card">
            <input
              placeholder="Title"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              required
            />
            <textarea
              placeholder="Description"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              required
            />
            <label>
              Type:
              <select
                value={form.type}
                onChange={(e) => setForm({ ...form, type: e.target.value })}
              >
                <option value="offer">Offer</option>
                <option value="request">Request</option>
                <option value="skill">Skill</option>
              </select>
            </label>
            <label>
              Free?
              <input
                type="checkbox"
                checked={form.is_free}
                onChange={(e) => setForm({ ...form, is_free: e.target.checked })}
              />
            </label>
            <label>
              Open to trade?
              <input
                type="checkbox"
                checked={form.is_trade}
                onChange={(e) => setForm({ ...form, is_trade: e.target.checked })}
              />
            </label>
            <button type="submit">Post listing</button>
          </form>
          <h2>Nearby listings</h2>
          <div className="list">
            {listings.map((l) => {
              const listingReactions = reactions[l.id] || { like: 0, helpful: 0, available: 0, unavailable: 0 };
              return (
                <div className="card" key={l.id}>
                  <h3>{l.title}</h3>
                  <p>{l.description}</p>
                  <p className="meta">
                    {l.type.toUpperCase()} · {l.is_free ? 'Free' : 'Paid/Trade'} · Status: {l.status}
                  </p>
                  <div className="reactions">
                    <button onClick={() => handleReaction('like', l.id)} className="reaction-btn">
                      👍 {listingReactions.like}
                    </button>
                    <button onClick={() => handleReaction('helpful', l.id)} className="reaction-btn">
                      ✅ {listingReactions.helpful}
                    </button>
                    <button onClick={() => handleReaction('available', l.id)} className="reaction-btn">
                      ✓ Available {listingReactions.available}
                    </button>
                    <button onClick={() => handleReaction('unavailable', l.id)} className="reaction-btn">
                      ✗ Used {listingReactions.unavailable}
                    </button>
                  </div>
                  {l.status === 'active' && (
                    <div className="status-actions">
                      <button onClick={() => handleUpdateStatus(l.id, 'reserved')} className="status-btn">
                        Mark as Reserved
                      </button>
                      <button onClick={() => handleUpdateStatus(l.id, 'completed')} className="status-btn">
                        Mark as Used Up
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
            {listings.length === 0 && <p>No nearby listings yet.</p>}
          </div>
        </section>
        <section className="column">
          <h2>Urgent need</h2>
          <form onSubmit={handleCreateUrgent} className="card urgent-card">
            <input
              placeholder="What do you need right now?"
              value={urgentForm.title}
              onChange={(e) => setUrgentForm({ ...urgentForm, title: e.target.value })}
              required
            />
            <textarea
              placeholder="Add a short description"
              value={urgentForm.description}
              onChange={(e) => setUrgentForm({ ...urgentForm, description: e.target.value })}
              required
            />
            <label>
              Radius (km)
              <input
                type="number"
                min="0.5"
                max="10"
                step="0.5"
                value={urgentForm.radius_km}
                onChange={(e) =>
                  setUrgentForm({ ...urgentForm, radius_km: Number(e.target.value) })
                }
              />
            </label>
            <button type="submit">Broadcast urgent need</button>
          </form>
          <h2>Urgent needs near you</h2>
          <div className="list">
            {urgent.map((u) => (
              <div className="card urgent" key={u.id}>
                <h3>{u.title}</h3>
                <p>{u.description}</p>
                <p className="meta">Within {u.radius_km} km</p>
                <button
                  onClick={() => handleGetMatchingListings(u.id)}
                  className="respond-btn"
                >
                  📋 Respond with my listing
                </button>
              </div>
            ))}
            {urgent.length === 0 && <p>No active urgent needs nearby.</p>}
          </div>
          {showRespondModal && matchingListings[showRespondModal] && (
            <div className="modal-overlay" onClick={() => setShowRespondModal(null)}>
              <div className="modal" onClick={(e) => e.stopPropagation()}>
                <h3>Select a listing to respond with:</h3>
                {matchingListings[showRespondModal].length > 0 ? (
                  <div className="modal-listings">
                    {matchingListings[showRespondModal].map((listing) => (
                      <div key={listing.id} className="modal-listing-item">
                        <strong>{listing.title}</strong>
                        <p>{listing.description}</p>
                        <p className="meta">
                          {listing.type} · {listing.is_free ? 'Free' : 'Paid'}
                        </p>
                        <button
                          onClick={() => handleRespondWithListing(showRespondModal, listing.id)}
                          className="select-listing-btn"
                        >
                          Use this listing
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p>No matching listings found. Create a listing first!</p>
                )}
                <button onClick={() => setShowRespondModal(null)} className="close-modal-btn">
                  Close
                </button>
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/*"
          element={
            <AuthGate>
              <Dashboard />
            </AuthGate>
          }
        />
      </Routes>
    </Router>
  );
}

export default App;
