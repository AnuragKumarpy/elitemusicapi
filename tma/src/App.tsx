import React, { useState, useEffect, useRef } from 'react';
import {
  Play, Pause, SkipForward, Square, Volume2, Sliders, Music,
  Radio, Sparkles, Disc3, Mic2, ListMusic, ThumbsUp, Users
} from 'lucide-react';

interface Track {
  id: string;
  title: string;
  artist: string;
  duration_seconds: number;
  thumbnail_url?: string;
  media_type: 'audio' | 'video';
  upvotes?: number;
}

interface DSPState {
  bass_boost_db: number;
  spatial_8d: boolean;
  speed: number;
  volume: number;
  nightcore: boolean;
}

export default function App() {
  const [isPlaying, setIsPlaying] = useState(true);
  const [progressSec, setProgressSec] = useState(48);
  const [activeTab, setActiveTab] = useState<'player' | 'dsp' | 'lyrics' | 'queue'>('player');
  const [activeLyricIndex, setActiveLyricIndex] = useState(3);
  const [wsConnected, setWsConnected] = useState(true);

  // DSP Sliders State
  const [dsp, setDsp] = useState<DSPState>({
    bass_boost_db: 4.5,
    spatial_8d: true,
    speed: 1.0,
    volume: 90,
    nightcore: false
  });

  const [currentTrack, setCurrentTrack] = useState<Track>({
    id: 'trk_starboy',
    title: 'Starboy (feat. Daft Punk)',
    artist: 'The Weeknd',
    duration_seconds: 230,
    thumbnail_url: 'https://images.unsplash.com/photo-1614613535308-eb5fbd3d2c17?w=500&auto=format&fit=crop&q=60',
    media_type: 'audio'
  });

  const [queue, setQueue] = useState<Track[]>([
    { id: '1', title: 'Blinding Lights', artist: 'The Weeknd', duration_seconds: 200, upvotes: 14, media_type: 'audio' },
    { id: '2', title: 'Midnight City', artist: 'M83', duration_seconds: 243, upvotes: 9, media_type: 'audio' },
    { id: '3', title: 'Get Lucky', artist: 'Daft Punk', duration_seconds: 248, upvotes: 6, media_type: 'audio' },
  ]);

  const lyrics = [
    { time: 10, text: "I'm tryna put you in the worst mood, ah" },
    { time: 25, text: "P1 cleaner than your church shoes, ah" },
    { time: 38, text: "Milli point two just to hurt you, ah" },
    { time: 48, text: "All red Lamb' just to tease you, ah" },
    { time: 60, text: "None of these toys on lease too, ah" },
    { time: 75, text: "Made your whole year in a week too, yah" },
  ];

  // Waveform canvas animation ref
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    let animId: number;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let phase = 0;
    const render = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const bars = 28;
      const barWidth = canvas.width / bars;

      for (let i = 0; i < bars; i++) {
        const height = isPlaying
          ? Math.sin(phase + i * 0.4) * 20 + 25 + Math.random() * (dsp.bass_boost_db * 2)
          : 6;
        const grad = ctx.createLinearGradient(0, 0, 0, canvas.height);
        grad.addColorStop(0, '#a855f7');
        grad.addColorStop(1, '#06b6d4');

        ctx.fillStyle = grad;
        ctx.fillRect(i * barWidth + 2, (canvas.height - height) / 2, barWidth - 4, height);
      }
      phase += 0.08;
      animId = requestAnimationFrame(render);
    };

    render();
    return () => cancelAnimationFrame(animId);
  }, [isPlaying, dsp]);

  // Simulate progress ticker
  useEffect(() => {
    if (!isPlaying) return;
    const interval = setInterval(() => {
      setProgressSec((p) => (p >= currentTrack.duration_seconds ? 0 : p + 1));
    }, 1000);
    return () => clearInterval(interval);
  }, [isPlaying, currentTrack]);

  const formatTime = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  const handleUpvote = (id: string) => {
    setQueue((prev) =>
      prev
        .map((t) => (t.id === id ? { ...t, upvotes: (t.upvotes || 0) + 1 } : t))
        .sort((a, b) => (b.upvotes || 0) - (a.upvotes || 0))
    );
  };

  return (
    <div style={{ maxWidth: '440px', margin: '0 auto', padding: '16px 14px', minHeight: '100vh' }}>
      {/* Header Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{
            width: '10px', height: '10px', borderRadius: '50%',
            backgroundColor: wsConnected ? '#22c55e' : '#ef4444',
            boxShadow: wsConnected ? '0 0 8px #22c55e' : 'none'
          }} />
          <span style={{ fontSize: '13px', fontWeight: 600, color: '#9ca3af', letterSpacing: '0.5px' }}>
            ELITE MUSIC LIVE
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'rgba(255,255,255,0.06)', padding: '4px 10px', borderRadius: '20px', fontSize: '12px' }}>
          <Users size={14} color="#a855f7" />
          <span style={{ fontWeight: 600 }}>18 in VC</span>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', background: 'rgba(255,255,255,0.04)', padding: '4px', borderRadius: '14px', marginBottom: '16px' }}>
        {[
          { id: 'player', label: 'DJ Deck', icon: Disc3 },
          { id: 'dsp', label: 'EQ / DSP', icon: Sliders },
          { id: 'lyrics', label: 'Lyrics', icon: Mic2 },
          { id: 'queue', label: 'Queue', icon: ListMusic },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              style={{
                flex: 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '5px',
                padding: '8px 0',
                border: 'none',
                background: isActive ? 'linear-gradient(135deg, #8b5cf6, #6366f1)' : 'transparent',
                color: isActive ? '#ffffff' : '#9ca3af',
                borderRadius: '10px',
                fontWeight: 600,
                fontSize: '12px',
                cursor: 'pointer',
                transition: 'all 0.2s ease'
              }}
            >
              <Icon size={14} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Main Tab Views */}
      {activeTab === 'player' && (
        <div className="glass-panel" style={{ padding: '20px', textAlign: 'center' }}>
          {/* Holographic Album Vinyl */}
          <div style={{ position: 'relative', width: '220px', height: '220px', margin: '0 auto 18px auto' }}>
            <div style={{
              width: '100%', height: '100%', borderRadius: '50%',
              backgroundImage: `url(${currentTrack.thumbnail_url})`,
              backgroundSize: 'cover',
              backgroundPosition: 'center',
              border: '4px solid rgba(168, 85, 247, 0.4)',
              boxShadow: isPlaying ? '0 0 35px rgba(168, 85, 247, 0.35)' : 'none',
              animation: isPlaying ? 'spin 12s linear infinite' : 'none',
            }} />
            <div style={{
              position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
              width: '45px', height: '45px', borderRadius: '50%', background: '#08080f',
              border: '2px solid rgba(255,255,255,0.2)'
            }} />
          </div>

          <h2 style={{ fontSize: '18px', fontWeight: 700, marginBottom: '4px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {currentTrack.title}
          </h2>
          <p style={{ color: '#9ca3af', fontSize: '13px', marginBottom: '14px' }}>
            {currentTrack.artist}
          </p>

          {/* Dynamic Waveform Visualizer */}
          <canvas ref={canvasRef} width={280} height={50} style={{ width: '100%', height: '50px', marginBottom: '12px' }} />

          {/* Progress Bar */}
          <div style={{ marginBottom: '14px' }}>
            <input
              type="range"
              min={0}
              max={currentTrack.duration_seconds}
              value={progressSec}
              onChange={(e) => setProgressSec(Number(e.target.value))}
              style={{ width: '100%' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#6b7280', marginTop: '4px' }}>
              <span>{formatTime(progressSec)}</span>
              <span>{formatTime(currentTrack.duration_seconds)}</span>
            </div>
          </div>

          {/* Transport Controls */}
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '18px' }}>
            <button
              onClick={() => setIsPlaying(!isPlaying)}
              style={{
                width: '56px', height: '56px', borderRadius: '50%',
                background: 'linear-gradient(135deg, #a855f7, #6366f1)',
                border: 'none', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
                cursor: 'pointer', boxShadow: '0 0 15px rgba(168, 85, 247, 0.4)'
              }}
            >
              {isPlaying ? <Pause size={24} /> : <Play size={24} style={{ marginLeft: '2px' }} />}
            </button>
            <button
              onClick={() => alert('Skipping to next track...')}
              style={{
                width: '42px', height: '42px', borderRadius: '50%',
                background: 'rgba(255,255,255,0.08)', border: 'none', color: '#fff',
                display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer'
              }}
            >
              <SkipForward size={18} />
            </button>
            <button
              onClick={() => alert('Ejecting voice stream and releasing assistant...')}
              style={{
                width: '42px', height: '42px', borderRadius: '50%',
                background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)',
                color: '#ef4444', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer'
              }}
            >
              <Square size={16} />
            </button>
          </div>
        </div>
      )}

      {/* DSP & EQ Sliders Tab */}
      {activeTab === 'dsp' && (
        <div className="glass-panel" style={{ padding: '20px' }}>
          <h3 style={{ fontSize: '15px', fontWeight: 700, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Sparkles size={16} color="#a855f7" /> Real-Time DSP Audio Modifiers
          </h3>

          {/* Bass Boost */}
          <div style={{ marginBottom: '18px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', marginBottom: '6px' }}>
              <span>🔊 Bass Boost</span>
              <span style={{ color: '#a855f7', fontWeight: 700 }}>+{dsp.bass_boost_db} dB</span>
            </div>
            <input
              type="range"
              min="0"
              max="15"
              step="0.5"
              value={dsp.bass_boost_db}
              onChange={(e) => setDsp({ ...dsp, bass_boost_db: parseFloat(e.target.value) })}
              style={{ width: '100%' }}
            />
          </div>

          {/* 8D Spatial Audio */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px', background: 'rgba(255,255,255,0.03)', borderRadius: '12px', marginBottom: '16px' }}>
            <div>
              <div style={{ fontSize: '13px', fontWeight: 600 }}>🎧 8D Spatial Audio</div>
              <div style={{ fontSize: '11px', color: '#6b7280' }}>Binaural 360° dynamic circular panning</div>
            </div>
            <input
              type="checkbox"
              checked={dsp.spatial_8d}
              onChange={(e) => setDsp({ ...dsp, spatial_8d: e.target.checked })}
              style={{ width: '20px', height: '20px', accentColor: '#a855f7', cursor: 'pointer' }}
            />
          </div>

          {/* Nightcore Mode */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px', background: 'rgba(255,255,255,0.03)', borderRadius: '12px', marginBottom: '16px' }}>
            <div>
              <div style={{ fontSize: '13px', fontWeight: 600 }}>⚡ Nightcore Mode</div>
              <div style={{ fontSize: '11px', color: '#6b7280' }}>High-tempo speed & pitch shift (1.25x)</div>
            </div>
            <input
              type="checkbox"
              checked={dsp.nightcore}
              onChange={(e) => setDsp({ ...dsp, nightcore: e.target.checked })}
              style={{ width: '20px', height: '20px', accentColor: '#a855f7', cursor: 'pointer' }}
            />
          </div>

          {/* Speed / Tempo */}
          <div style={{ marginBottom: '18px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', marginBottom: '6px' }}>
              <span>⏱️ Playback Speed</span>
              <span style={{ color: '#06b6d4', fontWeight: 700 }}>{dsp.speed}x</span>
            </div>
            <input
              type="range"
              min="0.75"
              max="1.5"
              step="0.05"
              value={dsp.speed}
              onChange={(e) => setDsp({ ...dsp, speed: parseFloat(e.target.value) })}
              style={{ width: '100%' }}
            />
          </div>

          {/* Volume */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', marginBottom: '6px' }}>
              <span>🔈 Stream Volume</span>
              <span style={{ color: '#10b981', fontWeight: 700 }}>{dsp.volume}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="150"
              value={dsp.volume}
              onChange={(e) => setDsp({ ...dsp, volume: parseInt(e.target.value) })}
              style={{ width: '100%' }}
            />
          </div>
        </div>
      )}

      {/* Synchronized Lyrics Tab */}
      {activeTab === 'lyrics' && (
        <div className="glass-panel" style={{ padding: '20px', height: '360px', overflowY: 'auto' }}>
          <h3 style={{ fontSize: '14px', color: '#9ca3af', marginBottom: '14px', textAlign: 'center' }}>
            🎤 Live Synced Lyrics (WebSocket Stream)
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', textAlign: 'center' }}>
            {lyrics.map((line, idx) => {
              const isCurrent = idx === activeLyricIndex;
              return (
                <div
                  key={idx}
                  onClick={() => setActiveLyricIndex(idx)}
                  style={{
                    fontSize: isCurrent ? '16px' : '14px',
                    fontWeight: isCurrent ? 800 : 400,
                    color: isCurrent ? '#a855f7' : '#4b5563',
                    textShadow: isCurrent ? '0 0 12px rgba(168, 85, 247, 0.4)' : 'none',
                    transition: 'all 0.3s ease',
                    cursor: 'pointer'
                  }}
                >
                  {line.text}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Collaborative Voting Queue Tab */}
      {activeTab === 'queue' && (
        <div className="glass-panel" style={{ padding: '16px' }}>
          <h3 style={{ fontSize: '15px', fontWeight: 700, marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <ListMusic size={16} color="#a855f7" /> Democratic Voting Queue
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {queue.map((track, i) => (
              <div
                key={track.id}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '10px 12px',
                  background: 'rgba(255,255,255,0.03)',
                  borderRadius: '10px'
                }}
              >
                <div>
                  <div style={{ fontSize: '13px', fontWeight: 600 }}>{track.title}</div>
                  <div style={{ fontSize: '11px', color: '#6b7280' }}>{track.artist} • {formatTime(track.duration_seconds)}</div>
                </div>
                <button
                  onClick={() => handleUpvote(track.id)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '4px',
                    padding: '6px 10px', borderRadius: '8px',
                    border: '1px solid rgba(168, 85, 247, 0.3)',
                    background: 'rgba(168, 85, 247, 0.1)',
                    color: '#a855f7', fontWeight: 700, fontSize: '12px', cursor: 'pointer'
                  }}
                >
                  <ThumbsUp size={12} /> {track.upvotes}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
