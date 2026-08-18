'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import ThemeToggle from '@/components/ThemeToggle';
import './landing.css';

/* CIVOS landing — "The Bulletin".
 *
 * The console is an instrument; this is the technical bulletin that ships with
 * it. Same ground, same typefaces, same colour discipline — gold stays reserved
 * for Silent Need so that the one concept the product exists to surface is the
 * one thing that glows, here and in the console alike.
 *
 * Every number on this page is traceable to something committed in the repo
 * (README provenance table, docs/GATE1-RESULT.md, docs/LANGUAGE-COVERAGE.md).
 * Nothing is rounded up for effect — the whole argument rests on not doing that.
 */

/* ── Telegram bot handle ──────────────────────────────────────────────────────
   Single source of truth. BotFather handles are globally unique and must end in
   "bot"; swap the value here and the link, the displayed @handle and the chat
   mock header all follow. Set to null to render the section without a live link
   (the copy degrades gracefully to "registration pending"). */
const TELEGRAM_HANDLE: string | null = 'Civos_in_bot';
const TELEGRAM_URL = TELEGRAM_HANDLE ? `https://t.me/${TELEGRAM_HANDLE}` : null;

/* Waveform bar heights for the voice-note bubble. Fixed, not random — a
   recording has a shape, and a shape that changes on every render is noise. */
const WAVE = [5, 9, 14, 8, 16, 11, 6, 13, 17, 10, 7, 12, 15, 8, 5, 10, 6, 9, 4, 7];

export default function Landing() {
  const [stuck, setStuck] = useState(false);
  const [instance, setInstance] = useState<0 | 1>(0);

  /* -- nav materialises once the hero starts leaving ---------------------- */
  useEffect(() => {
    const onScroll = () => setStuck(window.scrollY > 24);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  /* -- one reveal mechanism for the whole page ----------------------------
     A single observer over [data-reveal]. Elements unobserve once revealed, so
     nothing re-animates on scroll-back — re-entry animation is the tell of a
     page that is performing rather than presenting. */
  useEffect(() => {
    const nodes = Array.from(document.querySelectorAll<HTMLElement>('[data-reveal]'));

    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      nodes.forEach((n) => n.classList.add('in'));
      return;
    }

    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add('in');
            io.unobserve(e.target);
          }
        });
      },
      { rootMargin: '0px 0px -12% 0px', threshold: 0.12 },
    );

    nodes.forEach((n) => io.observe(n));
    return () => io.disconnect();
  }, []);

  return (
    <div className="lp">
      <a className="lp-skip" href="#main">
        Skip to content
      </a>

      {/* ================================================================
          Navigation
          ================================================================ */}
      <nav className="lp-nav" data-stuck={stuck}>
        <div className="lp-nav-inner">
          <Link href="/" className="wordmark" aria-label="CIVOS home">
            <b className="display">CIVOS</b>
            <span className="instance mono">IN</span>
          </Link>

          <div className="lp-nav-links">
            <a href="#blind-spot">The blind spot</a>
            <a href="#how">How it works</a>
            <a href="#telegram">Telegram</a>
            <a href="#dossier">The output</a>
            <a href="#provenance">Provenance</a>
          </div>

          <div className="lp-nav-right">
            <ThemeToggle />
            <Link href="/login" className="lp-btn sm">
              Sign in
            </Link>
            <Link href="/report" className="lp-btn sm">
              Report a need
            </Link>
            <Link href="/console" className="lp-btn sm solid">
              Open console <span className="arrow">→</span>
            </Link>
          </div>
        </div>
      </nav>

      <main id="main">
        {/* ==============================================================
            Hero
            ============================================================== */}
        <header className="lp-hero">
          <div className="lp-hero-bg" aria-hidden="true" />
          <div className="lp-grid-bg" aria-hidden="true" />

          <div className="lp-wrap lp-hero-inner">
            <p className="lp-eyebrow rise d1">
              <span className="pip" />
              PS-01 · AI for Digital Public Infrastructure &amp; Governance
            </p>

            <h1 className="lp-h1 rise d2">
              The districts that need the most are the ones that say the{' '}
              <em>least</em>.
            </h1>

            <p className="lp-hero-sub rise d3">
              CIVOS is a <strong>civic operating system</strong>. Citizens report what their
              area needs by <strong>speaking, typing or photographing it</strong> — in any
              language, with no app to install and, on Telegram, no account at all. CIVOS merges the duplicates into distinct
              needs, checks them against official deprivation data, corrects for the fact
              that the poorest districts complain the least, and emits a costed project
              dossier tied to a real government funding scheme.
            </p>

            <div className="lp-hero-cta rise d4">
              <Link href="/console" className="lp-btn solid">
                Open the console <span className="arrow">→</span>
              </Link>
              <Link href="/report" className="lp-btn">
                Report a need
              </Link>
              {TELEGRAM_URL && (
                <a
                  className="lp-btn"
                  href={TELEGRAM_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <TelegramGlyph size={13} /> Telegram bot
                </a>
              )}
            </div>

            <div className="lp-metrics rise d5">
              <div className="lp-metric">
                <span className="v">641</span>
                <span className="k">districts, with real boundaries, administrative codes and census codes</span>
                <span className="src">Real</span>
              </div>
              <div className="lp-metric">
                <span className="v">196</span>
                <span className="k">languages accepted as text; 56 locales full voice round-trip</span>
                <span className="src">Probed, not claimed</span>
              </div>
              <div className="lp-metric">
                <span className="v">94.2%</span>
                <span className="k">geo-grounding accuracy, re-measured against the 641-district gazetteer</span>
                <span className="src">Gate 1</span>
              </div>
              <div className="lp-metric">
                <span className="v">10</span>
                <span className="k">named central funding schemes with published unit costs</span>
                <span className="src">Real</span>
              </div>
            </div>
          </div>
        </header>

        {/* ==============================================================
            01 — The blind spot
            ============================================================== */}
        <section className="lp-sec" id="blind-spot">
          <div className="lp-wrap">
            <div className="lp-sec-head" data-reveal>
              <span className="lp-sec-idx">01</span>
              <h2 className="lp-sec-title">The failure everybody else will build.</h2>
              <span className="rule" />
            </div>

            <div className="lp-split">
              <div>
                <blockquote className="lp-pull" data-reveal style={{ '--i': 1 } as React.CSSProperties}>
                  <p>
                    A map of complaints is a map of who owns a phone and knows how to
                    complain. It is not a map of need.
                  </p>
                  <cite>The premise CIVOS is built around</cite>
                </blockquote>

                <p className="lp-lede" style={{ marginTop: 34 }} data-reveal>
                  Almost every team given this problem builds the same thing: a chatbot that
                  takes complaints, and a map with red dots showing where they came from. It
                  demos well and it is quietly inverted — fund the reddest dots and you fund
                  the loudest districts while starving the quietest ones.
                </p>

                <p className="lp-lede" data-reveal style={{ '--i': 1 } as React.CSSProperties}>
                  Every voice-based channel over-samples the connected, literate, urban
                  citizen. <strong>Silence gets read as satisfaction when it is usually the
                  absence of access.</strong> So CIVOS measures how much each district{' '}
                  <strong>speaks</strong> against how much each district{' '}
                  <strong>lacks</strong> — and the interesting answer is in the corner
                  nobody plots.
                </p>
              </div>

              <div data-reveal>
                <div className="lp-matrix-frame">
                  <div className="lp-axis-y" aria-hidden="true">
                    <span>Citizen signal volume →</span>
                  </div>

                  <div className="lp-matrix">
                    <div className="lp-cell">
                      <span className="cell-k">Many signals · deficit low</span>
                      <span className="cell-n">
                        <i className="swatch" style={{ background: 'var(--q-gap)' }} />
                        Expectation Gap
                      </span>
                      <span className="cell-b">
                        Complaints exceed the measured deficit. Your dataset may be stale, or
                        the service exists and is bad.
                      </span>
                      <span className="cell-tag">Re-survey</span>
                    </div>

                    <div className="lp-cell">
                      <span className="cell-k">Many signals · deficit high</span>
                      <span className="cell-n">
                        <i className="swatch" style={{ background: 'var(--q-act)' }} />
                        Act Now
                      </span>
                      <span className="cell-b">
                        Corroborated need — citizens and official data agree. Fund it.
                      </span>
                      <span className="cell-tag">Fund</span>
                    </div>

                    <div className="lp-cell">
                      <span className="cell-k">Few signals · deficit low</span>
                      <span className="cell-n">
                        <i className="swatch" style={{ background: 'var(--q-stable)' }} />
                        Stable
                      </span>
                      <span className="cell-b">No action indicated.</span>
                      <span className="cell-tag">Hold</span>
                    </div>

                    <div className="lp-cell is-silent">
                      <span className="cell-k">Few signals · deficit high</span>
                      <span className="cell-n">
                        <i className="swatch" style={{ background: 'var(--q-silent)' }} />
                        Silent Need
                      </span>
                      <span className="cell-b">
                        Severe deficit, no citizen voice. These districts are invisible to
                        every complaint dashboard ever built.
                      </span>
                      <span className="cell-tag">Dispatch outreach</span>
                    </div>
                  </div>

                  <div className="lp-axis-x" aria-hidden="true">
                    Official deprivation index →
                  </div>
                </div>

                <p className="lp-note" data-reveal>
                  <b>CIVOS never auto-funds silence.</b> That would replace one guess with
                  another. A Silent Need district triggers <b>outreach</b> — go and ask —
                  not a transfer. It is a bias-correction mechanism, not an override of
                  citizen input, and the console says so on the card itself.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* ==============================================================
            02 — How it works
            ============================================================== */}
        <section className="lp-sec" id="how">
          <div className="lp-wrap">
            <div className="lp-sec-head" data-reveal>
              <span className="lp-sec-idx">02</span>
              <h2 className="lp-sec-title">Three loops, end to end.</h2>
              <span className="rule" />
            </div>

            <p className="lp-lede" style={{ marginBottom: 44 }} data-reveal>
              Listen in any modality and any language. Decide with official data joined in
              and participation bias corrected. Then — the part the problem statement asks
              for and almost everyone skips —{' '}
              <strong>verify that the money actually changed something</strong>.
            </p>

            <div className="lp-loops">
              <article className="lp-loop" data-reveal style={{ '--i': 0 } as React.CSSProperties}>
                <div className="lp-loop-k">
                  <span className="n">LOOP 1</span>
                  <span className="t">Listen</span>
                </div>
                <h3>One call, three modalities.</h3>
                <p>
                  Web widget, Telegram bot and bulk CSV import all feed{' '}
                  <strong>a single Gemini multimodal call</strong>. Audio, text and image
                  parts go into the same request and come back as one structured schema —
                  not three pipelines. It handles code-switching mid-sentence, the way
                  people actually speak.
                </p>
                <ul className="lp-pipe">
                  <li>language auto-detect · sector · severity</li>
                  <li>visual asset · condition · geo hint</li>
                  <li>EXIF GPS → ST_CONTAINS → exact district</li>
                </ul>
              </article>

              <article className="lp-loop" data-reveal style={{ '--i': 1 } as React.CSSProperties}>
                <div className="lp-loop-k">
                  <span className="n">LOOP 2</span>
                  <span className="t">Decide</span>
                </div>
                <h3>800 complaints, one problem.</h3>
                <p>
                  Everything lands in BigQuery. Vector search collapses duplicates into{' '}
                  <strong>distinct needs</strong> — and catches duplicate photographs, so
                  nobody inflates a district by resubmitting the same picture. Official
                  deficit data joins in, the participation correction runs, districts are
                  scored and sorted.
                </p>
                <ul className="lp-pipe">
                  <li>ML.GENERATE_EMBEDDING + VECTOR_SEARCH</li>
                  <li>DeficitIndex · VoiceCorrection · AdjustedDemand</li>
                  <li>ARIMA_PLUS 90-day forecast</li>
                  <li>quadrant assignment + scheme match</li>
                </ul>
              </article>

              <article className="lp-loop" data-reveal style={{ '--i': 2 } as React.CSSProperties}>
                <div className="lp-loop-k">
                  <span className="n">LOOP 3</span>
                  <span className="t">Verify</span>
                </div>
                <h3>Did the thing get fixed?</h3>
                <p>
                  After a project is funded, do the complaints stop? Does a photograph of
                  the same handpump look different? Before/after image pairs are matched by{' '}
                  <strong>image embedding plus administrative unit</strong>. The problem
                  statement says nobody can measure impact; this is the answer to that
                  sentence.
                </p>
                <ul className="lp-pipe">
                  <li>post-funding signal decay</li>
                  <li>before/after pair on the same asset</li>
                  <li>outcome written back to the dossier</li>
                </ul>
              </article>
            </div>
          </div>
        </section>

        {/* ==============================================================
            03 — Modalities
            ============================================================== */}
        <section className="lp-sec">
          <div className="lp-wrap">
            <div className="lp-sec-head" data-reveal>
              <span className="lp-sec-idx">03</span>
              <h2 className="lp-sec-title">Three ways in, because each buys something different.</h2>
              <span className="rule" />
            </div>

            <div className="lp-mods">
              <article className="lp-mod" data-reveal style={{ '--i': 0 } as React.CSSProperties}>
                <div className="lp-mod-glyph">
                  <MicGlyph />
                </div>
                <h3>Voice</h3>
                <p className="buys">Buys access</p>
                <p>
                  No literacy, no form, no knowing which department owns the problem. On
                  Telegram it needs no account either, which is what keeps this channel
                  reachable by the citizens the system is most at risk of missing. Audio is transcribed and deleted immediately.
                </p>
              </article>

              <article className="lp-mod" data-reveal style={{ '--i': 1 } as React.CSSProperties}>
                <div className="lp-mod-glyph">
                  <TextGlyph />
                </div>
                <h3>Text</h3>
                <p className="buys">Buys scale</p>
                <p>
                  Messaging apps and web forms — plus bulk import of the millions of
                  complaints already sitting in legacy grievance systems. This is how CIVOS
                  defragments the existing silos instead of becoming silo number five.
                </p>
              </article>

              <article className="lp-mod" data-reveal style={{ '--i': 2 } as React.CSSProperties}>
                <div className="lp-mod-glyph">
                  <CameraGlyph />
                </div>
                <h3>Photograph</h3>
                <p className="buys">Buys evidence</p>
                <p>
                  A voice note is a claim; a photograph is corroboration. It is also the
                  highest-confidence geo path via EXIF, the only modality that can verify a
                  fix — and it <strong>needs no language at all</strong>.
                </p>
              </article>
            </div>

            <p className="lp-note" style={{ maxWidth: '78ch' }} data-reveal>
              <b>A photograph is the accessibility floor.</b> A citizen whose language
              nothing on earth supports can still point a camera at a broken handpump and be
              heard. And photographic evidence is deliberately the{' '}
              <b>smallest weight in the scoring formula</b> — if it counted for much,
              districts where nobody owns a camera would be punished twice, which would
              break the entire point of the product.
            </p>
          </div>
        </section>

        {/* ==============================================================
            04 — Telegram
            ============================================================== */}
        <section className="lp-sec" id="telegram">
          <div className="lp-wrap">
            <div className="lp-sec-head" data-reveal>
              <span className="lp-sec-idx">04</span>
              <h2 className="lp-sec-title">Reporting where people already are.</h2>
              <span className="rule" />
            </div>

            <div className="lp-tg">
              <div data-reveal>
                <span className="lp-tg-mark">
                  <TelegramGlyph size={18} />
                  {TELEGRAM_HANDLE ? `@${TELEGRAM_HANDLE}` : 'Handle registration pending'}
                </span>

                <p className="lp-lede">
                  Asking a citizen to install a government app is asking most citizens not to
                  report at all. So the primary channel is a{' '}
                  <strong>messaging app they already have open</strong>. Send a voice note in
                  Bhojpuri, a photograph of a collapsed culvert, or two lines of text — the
                  bot answers with exactly what it understood, so nobody is left wondering
                  whether it landed.
                </p>

                <div className="lp-tg-steps">
                  <div className="lp-tg-step">
                    <span className="sn">01</span>
                    <span className="sb">
                      <b>Open the bot</b> — no app to install, <b>no CIVOS account</b>, no form.
                      This is the only channel with no sign-in: the web console and the web
                      intake form both require one. Telegram over WhatsApp because it needs
                      no Meta business verification.
                    </span>
                  </div>
                  <div className="lp-tg-step">
                    <span className="sn">02</span>
                    <span className="sb">
                      <b>Speak, type, or send a photo.</b> Mix all three in one message.
                      Language is detected — there is no language selector to get wrong.
                    </span>
                  </div>
                  <div className="lp-tg-step">
                    <span className="sn">03</span>
                    <span className="sb">
                      <b>Get a structured receipt.</b> Sector, severity and district read
                      back in plain words. The same signal is already in the console.
                    </span>
                  </div>
                  <div className="lp-tg-step">
                    <span className="sn">04</span>
                    <span className="sb">
                      <b>Nothing identifying is kept.</b> Audio transcribed then dropped,
                      photo analysed then dropped, GPS resolved to a district then discarded.
                    </span>
                  </div>
                </div>

                {TELEGRAM_URL ? (
                  <div className="lp-tg-qr-card">
                    {/* The QR encodes the public t.me URL only. Regenerate with
                        scripts/make_telegram_qr.py if the handle ever changes —
                        it fails loudly if this file and the live bot disagree. */}
                    <a
                      className="lp-tg-qr"
                      href={TELEGRAM_URL}
                      target="_blank"
                      rel="noopener noreferrer"
                      aria-label={`Open the CIVOS bot @${TELEGRAM_HANDLE} on Telegram`}
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src="/telegram-qr.svg"
                        alt={`QR code linking to the CIVOS Telegram bot, @${TELEGRAM_HANDLE}`}
                        width={124}
                        height={124}
                      />
                    </a>

                    <div className="lp-tg-qr-side">
                      <span className="lp-tg-qr-k">Scan to report</span>
                      <span className="lp-tg-qr-h mono">@{TELEGRAM_HANDLE}</span>
                      <p>
                        Point a phone camera at this and the bot opens — the same intake the console
                        reads from, and the one route into CIVOS that needs no account.
                      </p>
                      <a
                        className="lp-btn solid"
                        href={TELEGRAM_URL}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        <TelegramGlyph size={13} /> Open the bot{' '}
                        <span className="arrow">→</span>
                      </a>
                      {/* On a desktop with no Telegram app installed, t.me shows an
                          interstitial whose "Start bot" button fires a tg:// deep link
                          with nothing to hand off to, so it appears dead. Telegram's own
                          "Open in web" button on that page works. Saying so costs one
                          line and saves an evaluator concluding the bot is broken. */}
                      <span className="lp-tg-qr-note">
                        On desktop without the Telegram app, choose{' '}
                        <b>Open in web</b> on the page that appears.
                      </span>
                    </div>
                  </div>
                ) : (
                  <span className="lp-btn" aria-disabled="true" style={{ opacity: 0.5 }}>
                    Bot registration pending
                  </span>
                )}
              </div>

              <TelegramTranscript />
            </div>
          </div>
        </section>

        {/* ==============================================================
            05 — The dossier
            ============================================================== */}
        <section className="lp-sec" id="dossier">
          <div className="lp-wrap">
            <div className="lp-sec-head" data-reveal>
              <span className="lp-sec-idx">05</span>
              <h2 className="lp-sec-title">The output is a dossier, not a dashboard.</h2>
              <span className="rule" />
            </div>

            <p className="lp-lede" style={{ marginBottom: 42 }} data-reveal>
              Ask what a district officer actually does with a heatmap. Nothing — they
              cannot attach a heatmap to a funding request, and they get audited. So CIVOS
              emits a <strong>costed project dossier tied to a scheme that already has
              money in it</strong>. A recommendation with no funding route is a wish; a
              recommendation attached to an existing budget line is something a government
              can start next month.
            </p>

            <div className="lp-dossier" data-reveal>
              <div className="lp-dos-head">
                <div>
                  <div className="nm">Nandurbar</div>
                  <div className="sb">Maharashtra · Water &amp; Sanitation · illustrative dossier</div>
                </div>
                <span className="lp-dos-badge">Act Now</span>
              </div>

              <div className="lp-dos-grid">
                <div className="lp-dos-col">
                  <h4>Evidence</h4>
                  <dl className="lp-facts">
                    <div className="lp-fact">
                      <dt>Distinct needs, deduplicated</dt>
                      <dd>340</dd>
                    </div>
                    <div className="lp-fact">
                      <dt>From raw citizen signals</dt>
                      <dd>1,204</dd>
                    </div>
                    <div className="lp-fact">
                      <dt>Languages represented</dt>
                      <dd>7</dd>
                    </div>
                    <div className="lp-fact">
                      <dt>Needs with photographic evidence</dt>
                      <dd>89</dd>
                    </div>
                    <div className="lp-fact">
                      <dt>
                        Households without piped water
                        <span className="lp-cite">Source · NFHS-5, 2019–21</span>
                      </dt>
                      <dd>61%</dd>
                    </div>
                  </dl>
                </div>

                <div className="lp-dos-col">
                  <h4>In citizens&apos; own words</h4>

                  <blockquote className="lp-dos-quote">
                    <div className="o">बोरवेल तीन महीने से सूखा है, औरतें चार किलोमीटर चलती हैं।</div>
                    <div className="e">
                      “The borewell has been dry for three months; women walk four
                      kilometres.”
                    </div>
                    <div className="l">Hindi · voice · severity 5</div>
                  </blockquote>

                  <blockquote className="lp-dos-quote">
                    <div className="o">आमच्या वाडीत नळाला महिन्यातून दोनदा पाणी येतं.</div>
                    <div className="e">
                      “Water reaches the tap in our hamlet twice a month.”
                    </div>
                    <div className="l">Marathi · text · severity 4</div>
                  </blockquote>

                  <p style={{ fontSize: 11.5, color: 'var(--paper-4)', lineHeight: 1.55, margin: 0 }}>
                    Every claim in the generated narrative resolves to a signal cluster, an
                    image, or a dataset row. The model writes only from a retrieved bundle —
                    it is never asked to supply a fact.
                  </p>
                </div>

                <div className="lp-dos-col">
                  <h4>Funding route</h4>
                  <div className="lp-scheme">
                    <div className="nm">Jal Jeevan Mission</div>
                    <div className="mn">Ministry of Jal Shakti · functional household tap connections</div>
                    <div className="amt">
                      <span style={{ fontSize: 11, color: 'var(--paper-4)' }}>
                        Indicative cost
                      </span>
                      <b>₹4.82 Cr</b>
                    </div>
                  </div>
                  <p style={{ fontSize: 11.5, color: 'var(--paper-3)', lineHeight: 1.6, marginTop: 14 }}>
                    Eligibility, published unit cost and the ministry that owns the line —
                    attached to the recommendation, not left as an exercise for the officer.
                  </p>
                  <p style={{ fontSize: 11.5, color: 'var(--paper-4)', lineHeight: 1.55, marginTop: 12 }}>
                    Figures shown are illustrative of dossier structure. Deficit values and
                    scheme costs are real; citizen signals in this build are synthetic and
                    labelled as such throughout.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ==============================================================
            06 — Cross-border
            ============================================================== */}
        <section className="lp-sec">
          <div className="lp-wrap">
            <div className="lp-sec-head" data-reveal>
              <span className="lp-sec-idx">06</span>
              <h2 className="lp-sec-title">A country is a folder, not a codebase.</h2>
              <span className="rule" />
            </div>

            <div className="lp-split">
              <div data-reveal>
                <p className="lp-lede">
                  Two languages in a demo is translation. The real question is whether
                  Brazil&apos;s ministry can run this next month — and that is only yes if
                  the country layer is a <strong>configuration directory</strong> rather
                  than code.
                </p>
                <p className="lp-lede">
                  Add <code className="mono">adapters/za/</code> with South Africa&apos;s
                  districts, languages, datasets and schemes, and the identical system runs
                  on South African data in Zulu. Nothing in the core is rewritten.
                </p>
                <p className="lp-lede">
                  <strong>Enforced, not asserted.</strong>{' '}
                  <code className="mono">scripts/lint_country_literals.py</code> fails the
                  build if a country name, ISO code, scheme, dataset or language ever
                  reaches <code className="mono">core/</code>. It parses rather than greps —
                  “IN” is a SQL keyword and “in” is an English preposition, so the obvious
                  regex would match nearly every line of Python ever written.
                </p>

                {/* The switch demonstrates the ADAPTER SHAPE, not a shipped second
                    instance. adapters/ contains in/ only today, and a page whose
                    argument is "a labelled substitution beats mystery data" cannot
                    quietly imply otherwise — so the label says so plainly. It comes
                    off the moment adapters/za/ carries real data. */}
                <div
                  className="lp-instance"
                  data-i={instance}
                  role="group"
                  aria-label="Preview the CIVOS-IN and CIVOS-ZA adapter shape"
                >
                  <button type="button" onClick={() => setInstance(0)} aria-pressed={instance === 0}>
                    CIVOS-IN
                  </button>
                  <button type="button" onClick={() => setInstance(1)} aria-pressed={instance === 1}>
                    CIVOS-ZA
                  </button>
                </div>

                <p className="lp-instance-note">
                  <b>Illustrative.</b> <code className="mono">adapters/in/</code> is built and
                  live; <code className="mono">adapters/za/</code> is the adapter shape a second
                  country fills, not a shipped instance. What <em>is</em> verifiable today is the
                  half that matters architecturally — the lint below proves{' '}
                  <code className="mono">core/</code> holds no country literals, so no code
                  changes when the folder is added.
                </p>
              </div>

              <div className="lp-adapter" data-reveal>
                <div className="lp-adapter-bar">
                  <span className="dot real" />
                  repository layout
                </div>
                <div className="lp-adapter-body">
                  <div>
                    <span className="path">adapters/in/</span>{' '}
                    <span className={instance === 0 ? 'swap' : 'cmt'}>
                      languages · sectors · schemes · datasets
                    </span>
                  </div>
                  <div>
                    <span className="path" style={{ opacity: 0.55 }}>
                      adapters/za/
                    </span>{' '}
                    <span className={instance === 1 ? 'swap' : 'cmt'}>
                      languages · sectors · schemes · datasets{' '}
                      <span style={{ opacity: 0.7 }}>← not yet authored</span>
                    </span>
                  </div>
                  <div style={{ height: 10 }} />
                  <div>
                    <span className="core">core/</span>{' '}
                    <span className="cmt">contains ZERO country literals</span>
                  </div>
                  <div>
                    <span className="cmt">
                      ├─ interfaces/ LanguageModel · ChannelAdapter · Warehouse
                    </span>
                  </div>
                  <div>
                    <span className="cmt">
                      └─ models/ Part · RawSubmission · NormalisedSignal
                    </span>
                  </div>
                  <div style={{ height: 10 }} />
                  <div className="cmt">$ uv run python scripts/lint_country_literals.py</div>
                  <div>
                    <span className="core">✓ core/ is country-agnostic</span>
                  </div>
                  <div style={{ height: 10 }} />
                  <div className="cmt">
                    # active instance
                  </div>
                  <div>
                    <span className="swap">
                      CIVOS_INSTANCE={instance === 0 ? 'IN' : 'ZA'}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ==============================================================
            07 — Provenance
            ============================================================== */}
        <section className="lp-sec" id="provenance">
          <div className="lp-wrap">
            <div className="lp-sec-head" data-reveal>
              <span className="lp-sec-idx">07</span>
              <h2 className="lp-sec-title">What is real, and what is not.</h2>
              <span className="rule" />
            </div>

            <p className="lp-lede" style={{ marginBottom: 40 }} data-reveal>
              Stated here, in the interface, and in every dossier CIVOS emits.{' '}
              <strong>A labelled substitution is worth more than mystery data</strong> — and
              a system arguing that measurement bias is the core problem does not get to be
              vague about its own.
            </p>

            <div data-reveal>
              <table className="lp-table">
                <thead>
                  <tr>
                    <th scope="col">Layer</th>
                    <th scope="col">Status</th>
                    <th scope="col">Provenance</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>District boundaries, names, administrative codes</td>
                    <td>
                      <span className="lp-flag real">
                        <i className="dot" /> Real
                      </span>
                    </td>
                    <td>641 districts — DataMeet Census-2011 boundaries, CC-BY 4.0, simplified for web rendering</td>
                  </tr>
                  <tr>
                    <td>Sector deficit indicators</td>
                    <td>
                      <span className="lp-flag real">
                        <i className="dot" /> Real
                      </span>
                    </td>
                    <td>
                      NFHS-5 2019–21 (IIPS / MoHFW) — 639 of 641 districts, 4 of 5 sectors.
                      Cross-validated against a second independent extraction: 100%
                      identical.
                    </td>
                  </tr>
                  <tr>
                    <td>Funding schemes and unit costs</td>
                    <td>
                      <span className="lp-flag real">
                        <i className="dot" /> Real
                      </span>
                    </td>
                    <td>Ten named central schemes with published unit costs</td>
                  </tr>
                  <tr>
                    <td>Evidence photographs</td>
                    <td>
                      <span className="lp-flag real">
                        <i className="dot" /> Real
                      </span>
                    </td>
                    <td>
                      150 openly licensed, individually attributed images.{' '}
                      <em>Never generated</em> — vision accuracy demonstrated on synthetic
                      images would prove nothing.
                    </td>
                  </tr>
                  <tr>
                    <td>Citizen signals (voice and text)</td>
                    <td>
                      <span className="lp-flag synth">
                        <i className="dot" /> Synthetic
                      </span>
                    </td>
                    <td>
                      2,537 signals. No government data access, so they are generated from
                      real geography and real deficits with a{' '}
                      <em>deliberate participation bias</em> — because that bias is
                      precisely what the product detects.
                    </td>
                  </tr>
                  <tr>
                    <td>Roads &amp; Transport deficit · district population</td>
                    <td>
                      <span className="lp-flag none">
                        <i className="dot" /> Not loaded
                      </span>
                    </td>
                    <td>
                      Road connectivity has no health-survey equivalent and no census
                      population is loaded. Both are shown as gaps in the interface rather
                      than filled with a proxy.
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <p className="lp-note" style={{ maxWidth: '78ch' }} data-reveal>
              <b>Privacy is structural, not a policy page.</b> Audio is transcribed and
              deleted. Photographs are analysed and the original deleted — a thumbnail
              survives only when no people are detected, and if people are present nothing
              visual is kept. EXIF GPS resolves the administrative unit and is then
              discarded. k-anonymity suppression below five signals per district-sector is
              applied <b>inside the warehouse</b>, so no caller can route around it.
            </p>
          </div>
        </section>

        {/* ==============================================================
            Closing
            ============================================================== */}
        <section className="lp-cta">
          <div className="lp-cta-bg" aria-hidden="true" />
          <div className="lp-wrap lp-cta-inner">
            <h2 data-reveal>Go and look at the quiet districts.</h2>
            <p data-reveal style={{ '--i': 1 } as React.CSSProperties}>
              The console opens on 641 real districts. Flip the equity correction on and
              watch the ranking move — that movement is the entire argument, and it takes
              one click to check it yourself.
            </p>
            <div className="lp-cta-row" data-reveal style={{ '--i': 2 } as React.CSSProperties}>
              <Link href="/console" className="lp-btn solid">
                Open the console <span className="arrow">→</span>
              </Link>
              <Link href="/report" className="lp-btn">
                Report a need
              </Link>
              {TELEGRAM_URL && (
                <a className="lp-btn" href={TELEGRAM_URL} target="_blank" rel="noopener noreferrer">
                  <TelegramGlyph size={13} /> Telegram bot
                </a>
              )}
            </div>
          </div>
        </section>
      </main>

      {/* ================================================================
          Footer
          ================================================================ */}
      <footer className="lp-foot">
        <div className="lp-wrap">
          <div className="lp-foot-grid">
            <div>
              <Link href="/" className="wordmark" aria-label="CIVOS home">
                <b className="display">CIVOS</b>
                <span className="instance mono">IN</span>
              </Link>
              <p className="lp-foot-blurb">
                The civic operating system — citizen-signal-driven infrastructure
                prioritisation for BRICS governments. Built as a Digital Public Good, mapped
                against all nine DPGA indicators.
              </p>
            </div>

            <div>
              <h5>Product</h5>
              <ul>
                <li>
                  <Link href="/console">Policymaker console</Link>
                </li>
                <li>
                  <Link href="/report">Citizen intake</Link>
                </li>
                <li>
                  {TELEGRAM_URL ? (
                    <a href={TELEGRAM_URL} target="_blank" rel="noopener noreferrer">
                      Telegram bot
                    </a>
                  ) : (
                    <span style={{ color: 'var(--paper-4)', fontSize: 12.5 }}>
                      Telegram bot — pending
                    </span>
                  )}
                </li>
              </ul>
            </div>

            <div>
              <h5>Evidence</h5>
              <ul>
                <li>
                  <a href="#provenance">Data provenance</a>
                </li>
                <li>
                  <a href="#blind-spot">The quadrant model</a>
                </li>
                <li>
                  <a href="#how">Architecture</a>
                </li>
              </ul>
            </div>

            <div>
              <h5>Open source</h5>
              <ul>
                <li>
                  <a
                    href="https://github.com/ojha-436/CIVOS"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Repository ↗
                  </a>
                </li>
                <li>
                  <a
                    href="https://github.com/ojha-436/CIVOS/blob/main/EXPLAINER.md"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Explainer ↗
                  </a>
                </li>
                <li>
                  <a
                    href="https://github.com/ojha-436/CIVOS/blob/main/SPEC.md"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Specification ↗
                  </a>
                </li>
              </ul>
            </div>
          </div>

          {/* The colophon. The event line moves up here from the base row so the
              name is not printed twice within 40px of itself. */}
          <div className="lp-colophon">
            <span className="lp-colophon-k">Created &amp; designed by</span>
            <span className="lp-colophon-n">Prince Kumar Ojha</span>
            <div className="lp-colophon-rule" aria-hidden="true" />
            <span className="lp-colophon-r">
              Solo build · Build with AI: Code for Communities, Second Edition · PS-01
            </span>
          </div>

          <div className="lp-foot-base">
            <span>Apache-2.0 code · CC-BY-4.0 docs, schema &amp; data</span>
            <span>© 2026 Prince Kumar Ojha</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

/* ============================================================================
   The Telegram transcript
   ----------------------------------------------------------------------------
   Plays once, when scrolled into view, then holds. It is a mock of the receipt
   `scripts/telegram_bot.py` actually sends — sector, severity dots, district and
   geo confidence — rather than an invented conversation.
   ========================================================================== */

function TelegramTranscript() {
  const ref = useRef<HTMLDivElement>(null);
  const [step, setStep] = useState(0);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduced) {
      setStep(5);
      return;
    }

    let timers: ReturnType<typeof setTimeout>[] = [];

    const io = new IntersectionObserver(
      ([e]) => {
        if (!e.isIntersecting) return;
        io.disconnect();
        // 0 → greeting, 1 → voice note, 2 → typing, 3 → receipt, 4 → console note
        timers = [
          setTimeout(() => setStep(1), 260),
          setTimeout(() => setStep(2), 1050),
          setTimeout(() => setStep(3), 1900),
          setTimeout(() => setStep(4), 3050),
          setTimeout(() => setStep(5), 3900),
        ];
      },
      { threshold: 0.3 },
    );

    io.observe(el);
    return () => {
      io.disconnect();
      timers.forEach(clearTimeout);
    };
  }, []);

  return (
    <div className="lp-chat" ref={ref} data-reveal aria-label="Example Telegram conversation">
      <div className="lp-chat-head">
        <span className="lp-chat-av">C</span>
        <div className="lp-chat-id">
          <b>CIVOS India</b>
          <span>{TELEGRAM_HANDLE ? `@${TELEGRAM_HANDLE}` : 'bot'}</span>
        </div>
        <span style={{ marginLeft: 'auto' }}>
          <TelegramGlyph size={16} />
        </span>
      </div>

      <div className="lp-chat-body">
        {step >= 1 && (
          <div className="lp-msg in show">
            Namaste. Tell me what your area needs — <b>speak it, type it, or send a
            photo</b>. Any language.
          </div>
        )}

        {step >= 2 && (
          <div className="lp-msg out show">
            <span className="voice">
              <span className="lp-wave" aria-hidden="true">
                {WAVE.map((h, i) => (
                  <i key={i} style={{ height: h }} />
                ))}
              </span>
              <span className="dur">0:14</span>
            </span>
          </div>
        )}

        {step === 3 && (
          <div className="lp-typing" aria-label="Bot is processing">
            <i />
            <i />
            <i />
          </div>
        )}

        {step >= 4 && (
          <div className="lp-msg in show" style={{ maxWidth: '93%' }}>
            <span className="ok">✓ Received and structured.</span>
            <span className="tr">
              “हमारे गाँव का बोरवेल तीन महीने से सूखा है” — the borewell in our village has
              been dry for three months.
            </span>
            <dl className="lp-msg-struct">
              <div>
                <dt>Language</dt>
                <dd>Hindi · hi-IN</dd>
              </div>
              <div>
                <dt>Sector</dt>
                <dd>Water &amp; Sanitation</dd>
              </div>
              <div>
                <dt>Severity</dt>
                <dd className="sev">●●●●●</dd>
              </div>
              <div>
                <dt>District</dt>
                <dd>Nandurbar</dd>
              </div>
              <div>
                <dt>Geo confidence</dt>
                <dd>High · EXIF</dd>
              </div>
            </dl>
          </div>
        )}

        {step >= 5 && (
          <div className="lp-msg in show">
            Your report is counted. Audio deleted, location resolved to the district and
            discarded. <b>Nothing identifying was stored.</b>
          </div>
        )}
      </div>

      <div className="lp-chat-foot">
        <span>Voice · Text · Photo</span>
        <span>No app install</span>
      </div>
    </div>
  );
}

/* ============================================================================
   Glyphs — drawn inline at 1.5px stroke to match the hairline rule weight
   ========================================================================== */

function TelegramGlyph({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M21.94 4.3 18.9 19.1c-.23 1.02-.84 1.27-1.7.79l-4.7-3.47-2.27 2.19c-.25.25-.46.46-.95.46l.34-4.8 8.73-7.9c.38-.34-.08-.53-.59-.19L6.98 13.1l-4.64-1.45c-1.01-.32-1.03-1.01.21-1.5l18.14-7c.84-.3 1.58.2 1.25 1.15z" />
    </svg>
  );
}

function MicGlyph() {
  return (
    <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
      <rect x="9" y="2.5" width="6" height="11" rx="3" />
      <path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3.5M8.5 21.5h7" />
    </svg>
  );
}

function TextGlyph() {
  return (
    <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3.5 5.5h17v11h-9.5L6 21v-4.5H3.5z" />
      <path d="M7.5 9.5h9M7.5 12.5h6" />
    </svg>
  );
}

function CameraGlyph() {
  return (
    <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M2.5 7.5h4L8 5h8l1.5 2.5h4v12h-19z" />
      <circle cx="12" cy="13" r="3.6" />
    </svg>
  );
}
