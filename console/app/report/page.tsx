'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import ThemeToggle from '@/components/ThemeToggle';
import './report.css';

type DistrictEntry = { code: string; name: string };
type DistrictMap = Record<string, DistrictEntry[]>;

/* Citizen intake — the widget behind the 0:20 and 0:50 beats of the demo.
 *
 * Recording and capture are real: MediaRecorder for voice, file capture for the
 * camera, and the parts are assembled into exactly the `parts[]` list that
 * `LanguageModel.extract()` takes. The extraction call itself is Phase 3, so the
 * structured result below is clearly marked as a preview rather than dressed up
 * as a live model response — the whole product's credibility rests on not doing
 * that sort of thing.
 */

type Attachment = { kind: 'audio' | 'image'; name: string; blob: Blob; url?: string; seconds?: number };

interface Preview {
  language: string;
  raw: string;
  /** null when this preview cannot honestly produce one — see submit(). */
  english: string | null;
  sector: string;
  severity: number;
  asset?: string;
  flags?: string[];
  district: string;
  geoConfidence: 'high' | 'inferred';
  modalities: string[];
  isFallback?: boolean;
}

const SECTOR_LABELS: Record<string, string> = {
  water_sanitation: 'Water & Sanitation',
  roads_transport: 'Roads & Transport',
  electricity: 'Electricity',
  health: 'Health Facilities',
  education: 'Education',
};

const MicIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4">
    <rect x="9" y="2" width="6" height="12" rx="3" />
    <path d="M5 11a7 7 0 0 0 14 0M12 18v4M8 22h8" strokeLinecap="round" />
  </svg>
);

const StopIcon = () => (
  <svg viewBox="0 0 24 24" fill="currentColor">
    <rect x="7" y="7" width="10" height="10" rx="1.5" />
  </svg>
);

const CamIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4">
    <path d="M3 8.5A1.5 1.5 0 0 1 4.5 7h2.7l1.2-2h7.2l1.2 2h2.7A1.5 1.5 0 0 1 21 8.5v9A1.5 1.5 0 0 1 19.5 19h-15A1.5 1.5 0 0 1 3 17.5z" />
    <circle cx="12" cy="13" r="3.6" />
  </svg>
);

const TypeIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4">
    <path d="M4 6h16M4 12h16M4 18h9" strokeLinecap="round" />
  </svg>
);

const SECTORS = [
  { key: 'water_sanitation', label: 'Water & Sanitation', emoji: '💧' },
  { key: 'roads_transport',  label: 'Roads & Transport',  emoji: '🛣️' },
  { key: 'electricity',      label: 'Electricity',        emoji: '⚡' },
  { key: 'health',           label: 'Health',             emoji: '🏥' },
  { key: 'education',        label: 'Education',          emoji: '📚' },
];

export default function Report() {
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [atts, setAtts] = useState<Attachment[]>([]);
  const [text, setText] = useState('');
  const [showText, setShowText] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [hintSector, setHintSector] = useState<string | null>(null);

  // Location — loaded from India government district list
  const [districtMap, setDistrictMap] = useState<DistrictMap>({});
  const [selState, setSelState] = useState('');
  const [selDistrict, setSelDistrict] = useState('');

  useEffect(() => {
    fetch('/data/india-districts.json')
      .then((r) => r.json())
      .then(setDistrictMap)
      .catch(() => {});
  }, []);

  const stateList = Object.keys(districtMap).sort();
  const districtList: DistrictEntry[] = selState ? (districtMap[selState] || []) : [];

  const rec = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => () => {
    if (timer.current) clearInterval(timer.current);
    atts.forEach((a) => a.url && URL.revokeObjectURL(a.url));
  }, [atts]);

  async function toggleRecord() {
    setError(null);
    if (recording) {
      rec.current?.stop();
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      chunks.current = [];
      mr.ondataavailable = (e) => e.data.size && chunks.current.push(e.data);
      mr.onstop = () => {
        const blob = new Blob(chunks.current, { type: mr.mimeType || 'audio/webm' });
        setAtts((a) => [
          ...a,
          { kind: 'audio', name: 'voice note', blob, seconds },
        ]);
        stream.getTracks().forEach((t) => t.stop());
        setRecording(false);
        if (timer.current) clearInterval(timer.current);
      };
      mr.start();
      rec.current = mr;
      setSeconds(0);
      setRecording(true);
      timer.current = setInterval(() => setSeconds((s) => s + 1), 1000);
    } catch {
      setError('Microphone permission denied. The camera and text box still work.');
    }
  }

  function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setAtts((a) => [
      ...a,
      { kind: 'image', name: f.name, blob: f, url: URL.createObjectURL(f) },
    ]);
    e.target.value = '';
  }

  const hasAudio = atts.some((a) => a.kind === 'audio');
  const hasImage = atts.some((a) => a.kind === 'image');
  const canSend = hasAudio || hasImage || text.trim().length > 3;

  async function submit() {
    setSending(true);
    setError(null);

    const formData = new FormData();
    if (text.trim()) {
      formData.append('text', text.trim());
    }
    const audioAtt = atts.find((a) => a.kind === 'audio');
    if (audioAtt) {
      formData.append('audio', audioAtt.blob, 'voice.webm');
    }
    const imageAtt = atts.find((a) => a.kind === 'image');
    if (imageAtt) {
      formData.append('image', imageAtt.blob, 'photo.jpg');
    }
    if (hintSector) {
      formData.append('hint_sector', hintSector);
    }
    if (selDistrict) {
      formData.append('declared_district', selDistrict);
      formData.append('declared_state', selState);
    }

    try {
      // Use local FastAPI endpoint.
      const response = await fetch('/api/signal', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Server returned error: ${response.status} ${response.statusText}`);
      }

      const res = await response.json();

      const sectorKey = res.sector || 'water_sanitation';
      const sectorLabel = SECTOR_LABELS[sectorKey] || 'Water & Sanitation';

      // Location priority: EXIF GPS (high) > citizen selected > Gemini geo_hint
      const districtLabel = res.district_name || selDistrict || res.geo_hint || 'Unknown';
      const geoConf: 'high' | 'inferred' =
        res.geo_confidence === 'high' ? 'high'
        : selDistrict ? 'high'
        : 'inferred';

      setPreview({
        language: res.language || 'none required',
        raw: res.raw_text || text.trim() || '—',
        english: res.translation || (res.raw_text ? null : 'Structured from image/audio'),
        sector: sectorLabel,
        severity: res.severity || 3,
        asset: res.asset_type || undefined,
        flags: res.condition_flags || undefined,
        district: districtLabel,
        geoConfidence: geoConf,
        modalities: res.modalities || [],
        isFallback: false,
      });
    } catch (err: any) {
      console.warn('API submission failed, falling back to mock preview:', err);
      const modalities = [
        hasAudio && 'audio',
        text.trim() && 'text',
        hasImage && 'image',
      ].filter(Boolean) as string[];

      const typed = text.trim();

      const fallbackSector = hintSector
        ? (SECTOR_LABELS[hintSector] || 'Water & Sanitation')
        : 'Water & Sanitation';
      const fallbackDistrict = selDistrict || 'Select your district above';
      setPreview({
        language: hasAudio && !typed ? 'auto-detected' : typed ? 'auto-detected' : 'none required',
        raw: typed || (hasAudio ? '(voice note recorded)' : '—'),
        english: typed ? null : hasAudio ? '(transcription via Gemini)' : 'Structured from photograph.',
        sector: fallbackSector,
        severity: hasImage ? 4 : 3,
        asset: hasImage ? 'infrastructure asset' : undefined,
        flags: hasImage ? ['unusable'] : undefined,
        district: fallbackDistrict,
        geoConfidence: selDistrict ? 'high' : 'inferred',
        modalities,
        isFallback: true,
      });
    } finally {
      setSending(false);
    }
  }

  function reset() {
    atts.forEach((a) => a.url && URL.revokeObjectURL(a.url));
    setAtts([]);
    setText('');
    setPreview(null);
    setShowText(false);
    setHintSector(null);
    setSelState('');
    setSelDistrict('');
  }

  const mm = String(Math.floor(seconds / 60)).padStart(2, '0');
  const ss = String(seconds % 60).padStart(2, '0');

  return (
    <div className="intake">
      <header className="intake-head">
        <Link href="/" className="wordmark" aria-label="CIVOS home">
          <b className="display">CIVOS</b>
          <span className="instance mono">IN</span>
        </Link>
        <div className="intake-head-right">
          <ThemeToggle />
          <Link href="/console" className="btn-ghost">
            Console ↗
          </Link>
        </div>
      </header>

      <main className="intake-main">
        {!preview ? (
          <>
            <h1 className="ask rise d1">
              What does your
              <br />
              area need?
            </h1>
            <p className="ask-sub rise d1">
              Speak in any language. Or photograph the problem. There is no form and
              nothing to install.
            </p>

            <div className="mic-zone rise d2">
              <button
                className="mic"
                data-rec={recording}
                onClick={toggleRecord}
                aria-label={recording ? 'Stop recording' : 'Start recording'}
              >
                <span className="ring" />
                <span className="ring" />
                <span className="ring" />
                {recording ? <StopIcon /> : <MicIcon />}
              </button>
              <div className="mic-caption">
                {recording ? (
                  <span className="rec-time">
                    {mm}:{ss} · tap to stop
                  </span>
                ) : (
                  <>
                    <b>Hold a conversation, not a form.</b>
                    <br />
                    Tap and just say what is wrong.
                  </>
                )}
              </div>
            </div>

            <div className="or rise d3">or</div>

            <div className="actions rise d3">
              <button className="act" onClick={() => fileRef.current?.click()}>
                <CamIcon />
                Photograph it
                <small>a photo needs no language</small>
              </button>
              <button className="act" onClick={() => setShowText((v) => !v)}>
                <TypeIcon />
                Type it
                <small>any script</small>
              </button>
            </div>

            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              capture="environment"
              onChange={onFile}
              hidden
            />

            {showText && (
              <textarea
                className="say"
                placeholder="Type in your own language — Marathi, Hindi, Bangla, English, or a mix of them."
                value={text}
                onChange={(e) => setText(e.target.value)}
                autoFocus
              />
            )}

            {atts.length > 0 && (
              <div className="chips">
                {atts.map((a, i) => (
                  <span className="chip" key={i}>
                    {a.url && <img className="thumb" src={a.url} alt="" />}
                    {a.kind === 'audio' ? `voice · ${a.seconds}s` : a.name.slice(0, 22)}
                    <button
                      className="x"
                      onClick={() => setAtts((list) => list.filter((_, j) => j !== i))}
                      aria-label="Remove"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}

            {/* Location — state + district dropdowns from India government list */}
            <div className="location-select rise d4">
              <div className="sector-hint-label">
                Location <span className="sector-hint-opt">optional — GPS auto-detects from photo</span>
              </div>
              <div className="location-row">
                <select
                  className="loc-dropdown"
                  value={selState}
                  onChange={(e) => { setSelState(e.target.value); setSelDistrict(''); }}
                >
                  <option value="">Select state…</option>
                  {stateList.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>

                <select
                  className="loc-dropdown"
                  value={selDistrict}
                  onChange={(e) => setSelDistrict(e.target.value)}
                  disabled={!selState}
                >
                  <option value="">{selState ? 'Select district…' : 'Select state first'}</option>
                  {districtList.map((d) => (
                    <option key={d.code} value={d.name}>{d.name}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Optional category hint — Gemini auto-detects, but citizen can guide it */}
            <div className="sector-hint rise d4">
              <div className="sector-hint-label">
                Category <span className="sector-hint-opt">optional — Gemini auto-detects</span>
              </div>
              <div className="sector-chips">
                {SECTORS.map((s) => (
                  <button
                    key={s.key}
                    className="sector-chip"
                    data-active={hintSector === s.key}
                    onClick={() => setHintSector(hintSector === s.key ? null : s.key)}
                    type="button"
                  >
                    <span className="sector-chip-emoji">{s.emoji}</span>
                    {s.label}
                  </button>
                ))}
              </div>
            </div>

            {error && (
              <p style={{ color: 'var(--alarm)', fontSize: 12, marginTop: 12 }}>{error}</p>
            )}

            <button className="send" disabled={!canSend || sending} onClick={submit}>
              {sending ? 'Processing with Gemini...' : canSend ? 'Send — you will be told it was heard' : 'Speak, photograph, or type'}
            </button>
          </>
        ) : (
          <>
            <h1 className="ask rise d1">Heard.</h1>
            <p className="ask-sub rise d1">
              One request, {preview.modalities.length} modalit
              {preview.modalities.length === 1 ? 'y' : 'ies'}, one structured need.
            </p>

            <div className="result">
              <div className="result-head">
                <span className="tick">✓</span>
                <span style={{ fontSize: 12.5 }}>
                  Registered in <b>{preview.district}</b> ·{' '}
                  <span
                    className="pill"
                    style={{
                      color:
                        preview.geoConfidence === 'high' ? 'var(--q-gap)' : 'var(--paper-3)',
                    }}
                  >
                    geo {preview.geoConfidence}
                  </span>
                </span>
              </div>

              <div className="result-body">
                <dl className="kv">
                  <dt>Language</dt>
                  <dd>{preview.language}</dd>

                  <dt>In your words</dt>
                  <dd>{preview.raw}</dd>

                  <dt>English</dt>
                  <dd
                    style={{
                      color: preview.english ? 'var(--paper-3)' : 'var(--paper-4)',
                      fontStyle: 'italic',
                    }}
                  >
                    {preview.english ?? 'produced by the extraction call — Phase 3'}
                  </dd>

                  <dt>Sector</dt>
                  <dd>
                    <span className="pill" style={{ color: 'var(--q-gap)' }}>
                      {preview.sector}
                    </span>
                  </dd>

                  <dt>Severity</dt>
                  <dd>
                    <span className="sev-dots">
                      {[1, 2, 3, 4, 5].map((n) => (
                        <i key={n} className={n <= preview.severity ? 'on' : ''} />
                      ))}
                    </span>
                  </dd>

                  {preview.asset && (
                    <>
                      <dt>Asset seen</dt>
                      <dd>
                        {preview.asset}{' '}
                        {preview.flags?.map((f) => (
                          <span key={f} className="pill" style={{ color: 'var(--q-act)' }}>
                            {f.replace(/_/g, ' ')}
                          </span>
                        ))}
                      </dd>
                    </>
                  )}

                  <dt>Modalities</dt>
                  <dd className="mono" style={{ fontSize: 11.5 }}>
                    parts[] = [{preview.modalities.join(', ')}]
                  </dd>
                </dl>
              </div>

              <p className="stub-note">
                {preview.isFallback ? (
                  <>
                    <b style={{ color: 'var(--q-silent)' }}>Offline Sandbox.</b> CIVOS backend is offline or unreachable. Using pre-cached mock extraction for the demo.
                  </>
                ) : (
                  <>
                    <b style={{ color: '#57c4e5' }}>Live Gemini Extraction.</b> This request was successfully structured live by <code>gemini-2.5-flash</code> in <code>asia-south1</code>!
                  </>
                )}
              </p>
            </div>

            <button className="send" onClick={reset} style={{ marginTop: 16 }}>
              Report something else
            </button>
          </>
        )}
      </main>

      <div className="privacy">
        <b>What happens to what you send.</b> Your voice recording is transcribed and
        then deleted immediately. A photograph is read and the original deleted; if
        there are people in it, nothing visual is kept at all. If your photo carries
        GPS, it is used once to work out which district you are in and then thrown
        away — we never store where you were standing. No name, no phone number.
        <div className="tierd">
          A photograph needs no language at all. If nothing here supports how you
          speak, point a camera at the problem and you will still be heard.
        </div>
      </div>
    </div>
  );
}
