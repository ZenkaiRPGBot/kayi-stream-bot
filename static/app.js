/**
 * Kayi Stream - Premium Telegram Mini App & Web Player
 * Clean, Bright & Minimal Single Page Application
 * Apple / Linear Light Design Architecture
 */

(function () {
  'use strict';

  // Telegram Mini App SDK Setup
  const tg = window.Telegram?.WebApp;
  if (tg) {
    try {
      tg.ready();
      tg.expand();
      if (tg.setHeaderColor) tg.setHeaderColor('#FFFFFF');
      if (tg.setBackgroundColor) tg.setBackgroundColor('#F8FAFC');
    } catch (e) {
      console.warn('[WebApp] Setup note:', e);
    }
  }

  // DOM Elements - Shell & Views
  const viewDashboard = document.getElementById('viewDashboard');
  const viewPlayer = document.getElementById('viewPlayer');
  const userGreetingEl = document.getElementById('userGreeting');
  const userAvatarEl = document.getElementById('userAvatar');
  const userProfileBadge = document.getElementById('userProfileBadge');

  // DOM Elements - Dashboard Segmented Tabs
  const tabDashFiles = document.getElementById('tabDashFiles');
  const tabDashSettings = document.getElementById('tabDashSettings');
  const dashContentFiles = document.getElementById('dashContentFiles');
  const dashContentSettings = document.getElementById('dashContentSettings');

  // DOM Elements - Preferences & Preview
  const dashSubPreviewCard = document.getElementById('dashSubPreviewCard');
  const dashSubPreviewText = document.getElementById('dashSubPreviewText');
  const prefAutoResume = document.getElementById('prefAutoResume');

  // DOM Elements - Search
  const searchInput = document.getElementById('searchInput');
  const searchClearBtn = document.getElementById('searchClearBtn');
  const fileLibraryGrid = document.getElementById('fileLibraryGrid');
  const filesCountBadge = document.getElementById('filesCountBadge');
  const emptyStateCard = document.getElementById('emptyStateCard');

  // DOM Elements - Player View
  const btnBackLibrary = document.getElementById('btnBackLibrary');
  const playerVideoTitle = document.getElementById('playerVideoTitle');
  const moviPlayer = document.getElementById('moviPlayer');
  const nativeFallback = document.getElementById('nativeFallback');
  const playerCanvas = document.getElementById('playerCanvas');
  const playerLoadingSpinner = document.getElementById('playerLoadingSpinner');
  const playerErrorOverlay = document.getElementById('playerErrorOverlay');
  const btnExitFullscreen = document.getElementById('btnExitFullscreen');

  // Player Bottom Action Buttons
  const btnDownloadMain = document.getElementById('btnDownloadMain');
  const btnOpenBrowser = document.getElementById('btnOpenBrowser');
  const btnCopyLinkMain = document.getElementById('btnCopyLinkMain');
  const btnTracksBottom = document.getElementById('btnTracksBottom');
  const btnExternalPlayer = document.getElementById('btnExternalPlayer');

  // Audio & Subtitle Track Modal / Bottom Sheet
  const trackModalBackdrop = document.getElementById('trackModalBackdrop');
  const trackSheetContainer = document.getElementById('trackSheetContainer');
  const btnCloseTrackSheet = document.getElementById('btnCloseTrackSheet');
  const tabBtnAudio = document.getElementById('tabBtnAudio');
  const tabBtnSubs = document.getElementById('tabBtnSubs');
  const trackSectionAudio = document.getElementById('trackSectionAudio');
  const trackSectionSubs = document.getElementById('trackSectionSubs');
  const audioTracksList = document.getElementById('audioTracksList');
  const subTracksList = document.getElementById('subTracksList');
  const subPreviewText = document.getElementById('subPreviewText');

  // Confirmation Dialog
  const confirmBackdrop = document.getElementById('confirmBackdrop');
  const btnCancelDelete = document.getElementById('btnCancelDelete');
  const btnConfirmDelete = document.getElementById('btnConfirmDelete');

  // Toast
  const toastPill = document.getElementById('toastPill');
  const toastMsg = document.getElementById('toastMsg');

  // State Management
  let currentUser = tg?.initDataUnsafe?.user || null;
  let allFiles = [];
  let currentActiveFile = null;
  let currentTracksData = null;
  let activeAudioIndex = 0;
  let activeSubIndex = -1; // -1 = Off
  let activeSubSize = localStorage.getItem('kayi_sub_size') || 'normal';
  let activeSubColor = localStorage.getItem('kayi_sub_color') || '#FFFFFF';
  let activeSubBg = localStorage.getItem('kayi_sub_bg') || 'shadow';
  let activeSeekDuration = parseInt(localStorage.getItem('kayi_seek_duration') || '10', 10);
  let hideControlsTimer = null;
  let pendingDeleteFileId = null;

  const SPEED_OPTIONS = [1.0, 1.25, 1.5, 2.0, 0.75];
  let currentSpeedIndex = 0;

  // Haptic feedback helper
  function triggerHaptic(type = 'light') {
    if (!tg?.HapticFeedback) return;
    try {
      if (type === 'light') tg.HapticFeedback.impactOccurred('light');
      else if (type === 'medium') tg.HapticFeedback.impactOccurred('medium');
      else if (type === 'success') tg.HapticFeedback.notificationOccurred('success');
      else if (type === 'select') tg.HapticFeedback.selectionChanged();
    } catch (_) {}
  }

  // Toast notification
  function showToast(message) {
    if (!toastPill || !toastMsg) return;
    toastMsg.textContent = message;
    toastPill.classList.add('visible');
    triggerHaptic('light');
    clearTimeout(toastPill._timer);
    toastPill._timer = setTimeout(() => {
      toastPill.classList.remove('visible');
    }, 2200);
  }

  // Time formatter: H:MM:SS or M:SS
  function formatTime(seconds) {
    if (isNaN(seconds) || !isFinite(seconds) || seconds < 0) return '0:00';
    const s = Math.floor(seconds);
    const m = Math.floor(s / 60);
    const h = Math.floor(m / 60);
    const remM = m % 60;
    const remS = s % 60;
    const padS = remS < 10 ? '0' + remS : remS;
    if (h > 0) {
      const padM = remM < 10 ? '0' + remM : remM;
      return `${h}:${padM}:${padS}`;
    }
    return `${remM}:${padS}`;
  }

  // Browser download trigger (bypasses Telegram WebView sandbox)
  function triggerBrowserDownload(url) {
    if (!url) return;
    triggerHaptic('medium');
    showToast('Opening download in browser...');
    if (tg?.openLink) {
      try {
        tg.openLink(url);
        return;
      } catch (e) {
        console.warn('[WebApp] openLink note:', e);
      }
    }
    const win = window.open(url, '_blank');
    if (!win) {
      window.location.href = url;
    }
  }

  // Playback Progress Persistence (Keyed by file_unique_id or file_id)
  let hasResumedCurrentVideo = false;

  function getFileProgressKey(file) {
    if (!file) return null;
    const identifier = file.file_unique_id || file.file_id || `${file.name}_${file.size}`;
    return `kayi_resume_pos_${identifier}`;
  }

  function savePlaybackProgress() {
    if (!currentActiveFile) return;
    const playerEl = (moviPlayer && moviPlayer.style.display !== 'none') ? moviPlayer : nativeFallback;
    if (!playerEl) return;
    const cur = playerEl.currentTime;
    const dur = playerEl.duration;
    if (cur > 3 && isFinite(dur) && cur < dur - 8) {
      const key = getFileProgressKey(currentActiveFile);
      if (key) {
        try {
          localStorage.setItem(key, cur.toFixed(1));
        } catch (_) {}
      }
    }
  }

  function checkAndResumeProgress(file) {
    if (hasResumedCurrentVideo || !file) return;
    let seekTarget = null;

    // 0. Check file.resume_time (injected directly by server from ?t=)
    if (file.resume_time && isFinite(file.resume_time) && file.resume_time > 0) {
      seekTarget = file.resume_time;
    }

    // 1. Check URL query param ?t= or hash #t= (e.g. from "Open in Browser")
    if (seekTarget === null) {
      try {
        const urlParams = new URLSearchParams(window.location.search);
        const tStr = urlParams.get('t');
        if (tStr) {
          const val = parseFloat(tStr);
          if (isFinite(val) && val > 0) seekTarget = val;
        } else if (window.location.hash.startsWith('#t=')) {
          const val = parseFloat(window.location.hash.slice(3));
          if (isFinite(val) && val > 0) seekTarget = val;
        }
      } catch (_) {}
    }

    // 2. Check local progress store (if auto-resume preference is enabled)
    const autoResumeEnabled = localStorage.getItem('kayi_auto_resume') !== 'false';
    if (seekTarget === null && autoResumeEnabled) {
      const key = getFileProgressKey(file);
      if (key) {
        try {
          const saved = parseFloat(localStorage.getItem(key));
          if (saved && isFinite(saved) && saved > 2) seekTarget = saved;
        } catch (_) {}
      }
    }

    if (seekTarget === null || seekTarget <= 2) return;

    try {
      const playerEl = (moviPlayer && moviPlayer.style.display !== 'none') ? moviPlayer : nativeFallback;
      if (!playerEl) return;
      const dur = playerEl.duration;
      if (seekTarget > 0 && (!isFinite(dur) || dur <= 0 || seekTarget < dur - 3)) {
        hasResumedCurrentVideo = true;
        playerEl.currentTime = seekTarget;
        showToast(`Resumed from ${formatTime(seekTarget)}`);

        // Re-check after brief delay in case player was mid-demux initialization
        setTimeout(() => {
          if (playerEl && Math.abs(playerEl.currentTime - seekTarget) > 3) {
            try { playerEl.currentTime = seekTarget; } catch (_) {}
          }
        }, 800);
      }
    } catch (_) {}
  }

  // ==============================================================================
  // USER SETUP & ROUTING
  // ==============================================================================

  function initUser() {
    if (currentUser && currentUser.first_name) {
      const name = currentUser.first_name.trim();
      userGreetingEl.textContent = `Hello, ${name}!`;
      userAvatarEl.textContent = name.charAt(0).toUpperCase();
      userProfileBadge.style.display = 'flex';
    } else {
      userGreetingEl.textContent = 'Welcome to Kayi Stream';
      userProfileBadge.style.display = 'none';
    }
  }

  function setupTelegramBackButton() {
    if (!tg?.BackButton) return;
    tg.BackButton.onClick(() => {
      if (isFullscreenActive()) {
        exitFullscreenMode();
        return;
      }
      showDashboardView();
      triggerHaptic('select');
    });
  }

  function showDashboardView() {
    exitFullscreenMode();
    viewDashboard.classList.add('active');
    viewPlayer.classList.remove('active');
    closeTrackSheet();
    if (moviPlayer) {
      try { moviPlayer.pause(); } catch (_) {}
    }
    if (nativeFallback) {
      try { nativeFallback.pause(); } catch (_) {}
    }
    if (tg?.BackButton) {
      tg.BackButton.hide();
    }
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function showPlayerView(file) {
    currentActiveFile = file;
    viewDashboard.classList.remove('active');
    viewPlayer.classList.add('active');

    if (tg?.BackButton) {
      tg.BackButton.show();
    }

    // Set player metadata
    playerVideoTitle.textContent = file.name;
    btnDownloadMain.onclick = (e) => {
      e.preventDefault();
      triggerBrowserDownload(file.dl_url);
    };

    if (btnOpenBrowser) {
      btnOpenBrowser.onclick = (e) => {
        e.preventDefault();
        openInWebBrowser(file);
      };
    }

    btnCopyLinkMain.onclick = () => {
      const copyUrl = file.watch_url || `${window.location.origin}/watch/${file.display_id || file.id}`;
      copyToClipboard(copyUrl);
      showToast('Watch link copied to clipboard');
    };

    if (btnTracksBottom) {
      btnTracksBottom.onclick = (e) => {
        e.preventDefault();
        populateTrackSheetFromMovi();
      };
    }

    btnExternalPlayer.onclick = () => {
      openExternalPlayerModal(file);
    };

    // Load and play video in Movi WebAssembly Player
    loadVideoSource(file);

    // Probe tracks for backup info
    probeMediaTracks(file.display_id || file.id);

    window.scrollTo({ top: 0, behavior: 'smooth' });
    triggerHaptic('medium');
  }

  if (btnBackLibrary) {
    btnBackLibrary.addEventListener('click', () => {
      showDashboardView();
      triggerHaptic('light');
    });
  }

  // ==============================================================================
  // MY FILES & SEARCH
  // ==============================================================================

  async function loadUserFiles() {
    const userId = currentUser?.id || '986380678';
    try {
      const res = await fetch(`/api/user/files?user_id=${userId}`);
      const data = await res.json();
      if (data.status === 'success' && data.files && data.files.length > 0) {
        allFiles = data.files;
      } else {
        allFiles = [];
      }
    } catch (err) {
      console.warn('[Files] Load error:', err);
      allFiles = [];
    }

    // If initial file was passed via watch URL, make sure it is in allFiles
    if (window.__INITIAL_FILE__) {
      const initF = window.__INITIAL_FILE__;
      const exists = allFiles.some((f) => f.display_id === initF.display_id || String(f.id) === String(initF.id));
      if (!exists) {
        allFiles.unshift(initF);
      }
    }

    renderFileList(allFiles);
  }

  function renderFileList(files) {
    fileLibraryGrid.innerHTML = '';
    filesCountBadge.textContent = files.length;

    if (!files || files.length === 0) {
      emptyStateCard.style.display = 'flex';
      return;
    }

    emptyStateCard.style.display = 'none';

    files.forEach((file) => {
      const card = document.createElement('div');
      card.className = 'file-card';

      const isVideo = file.category === 'video' || file.name.match(/\.(mp4|mkv|webm|avi|mov|ts)$/i);
      const isAudio = file.category === 'audio' || file.name.match(/\.(mp3|m4a|aac|wav|flac|opus)$/i);

      let iconSvg = isVideo
        ? `<svg class="lucide" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m22 8-6 4 6 4V8Z"/><rect width="14" height="12" x="2" y="6" rx="2"/></svg>`
        : `<svg class="lucide" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/></svg>`;

      const ext = file.name.split('.').pop().toUpperCase() || 'FILE';

      card.innerHTML = `
        <div class="file-card-left">
          <div class="file-type-icon-box ${isVideo ? 'video' : ''}">
            ${iconSvg}
          </div>
          <div class="file-card-details">
            <div class="file-card-name" title="${escapeHtml(file.name)}">${escapeHtml(file.name)}</div>
            <div class="file-card-meta">
              <span>${file.size_fmt}</span>
              <span class="file-card-meta-dot">•</span>
              <span>${ext}</span>
              <span class="file-card-meta-dot">•</span>
              <span>Ref: ${file.display_id}</span>
            </div>
          </div>
        </div>
        <div class="file-card-actions">
          ${isVideo ? `<button class="btn-action-primary btn-play-card" aria-label="Watch Video">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
            <span>Watch</span>
          </button>` : ''}
          <button class="btn-action-secondary btn-card-download" aria-label="Download File">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/></svg>
          </button>
          <button class="btn-more-menu" aria-label="More options">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/></svg>
          </button>
          <div class="dropdown-menu-wrapper">
            <button class="dropdown-item btn-dd-watch">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
              <span>Watch Video</span>
            </button>
            <button class="dropdown-item btn-dd-download">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/></svg>
              <span>Download File</span>
            </button>
            <button class="dropdown-item btn-dd-copy">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>
              <span>Copy Link</span>
            </button>
            <button class="dropdown-item btn-dd-vlc">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" x2="21" y1="14" y2="3"/></svg>
              <span>Open in VLC</span>
            </button>
            <button class="dropdown-item danger btn-dd-remove">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
              <span>Remove File</span>
            </button>
          </div>
        </div>
      `;

      // Event Listeners
      const playBtn = card.querySelector('.btn-play-card');
      if (playBtn) {
        playBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          showPlayerView(file);
        });
      }

      const dlBtn = card.querySelector('.btn-card-download');
      if (dlBtn) {
        dlBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          triggerBrowserDownload(file.dl_url);
        });
      }

      const moreBtn = card.querySelector('.btn-more-menu');
      const menu = card.querySelector('.dropdown-menu-wrapper');

      moreBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        closeAllDropdowns();
        menu.classList.toggle('open');
      });

      card.querySelector('.btn-dd-watch')?.addEventListener('click', (e) => {
        e.stopPropagation();
        menu.classList.remove('open');
        showPlayerView(file);
      });

      card.querySelector('.btn-dd-download')?.addEventListener('click', (e) => {
        e.stopPropagation();
        menu.classList.remove('open');
        triggerBrowserDownload(file.dl_url);
      });

      card.querySelector('.btn-dd-copy')?.addEventListener('click', (e) => {
        e.stopPropagation();
        menu.classList.remove('open');
        const copyUrl = file.watch_url || `${window.location.origin}/watch/${file.display_id || file.id}`;
        copyToClipboard(copyUrl);
        showToast('Watch link copied to clipboard');
      });

      card.querySelector('.btn-dd-vlc')?.addEventListener('click', (e) => {
        e.stopPropagation();
        menu.classList.remove('open');
        openExternalVlc(file.stream_url);
      });

      card.querySelector('.btn-dd-remove')?.addEventListener('click', (e) => {
        e.stopPropagation();
        menu.classList.remove('open');
        askDeleteConfirmation(file.display_id || file.id);
      });

      card.addEventListener('click', () => {
        if (isVideo) {
          showPlayerView(file);
        } else {
          triggerBrowserDownload(file.dl_url);
        }
      });

      fileLibraryGrid.appendChild(card);
    });
  }

  function closeAllDropdowns() {
    document.querySelectorAll('.dropdown-menu-wrapper.open').forEach((el) => {
      el.classList.remove('open');
    });
  }

  document.addEventListener('click', () => closeAllDropdowns());

  // Search filtering & link pasting
  searchInput.addEventListener('input', (e) => {
    const val = e.target.value.trim().toLowerCase();
    searchClearBtn.classList.toggle('visible', val.length > 0);

    if (!val) {
      renderFileList(allFiles);
      return;
    }

    // Direct link or ID detection
    if (val.includes('/watch/') || val.includes('/stream/') || val.match(/^[0-9]{8,15}$/)) {
      // Clean ID extracted
      let extractedId = val;
      if (val.includes('/watch/')) extractedId = val.split('/watch/')[1].split(/[?#]/)[0];
      else if (val.includes('/stream/')) extractedId = val.split('/stream/')[1].split(/[?#]/)[0];

      const match = allFiles.find((f) => f.display_id === extractedId || String(f.id) === extractedId);
      if (match) {
        renderFileList([match]);
        return;
      }
    }

    const filtered = allFiles.filter((f) => f.name.toLowerCase().includes(val) || (f.display_id && f.display_id.includes(val)));
    renderFileList(filtered);
  });

  searchClearBtn.addEventListener('click', () => {
    searchInput.value = '';
    searchClearBtn.classList.remove('visible');
    renderFileList(allFiles);
    searchInput.focus();
  });

  // ==============================================================================
  // MOVI PLAYER + JASSUB LIBASS SUBTITLE ENGINE (WASM + WebCodecs)
  // ==============================================================================

  let activeSubTrackId = null; // null = Off, or integer track id
  let activeAudioTrackId = null;

  async function ensureMoviPlayerReady() {
    if (customElements.get('movi-player')) return;
    try {
      await Promise.race([
        customElements.whenDefined('movi-player'),
        new Promise((res) => setTimeout(res, 4000))
      ]);
    } catch (_) {}
  }

  // JASSUB Worker URL Loader
  let jassubWorkerBlobUrl = null;
  let jassubWorkerPromise = null;
  async function getJassubWorkerUrl() {
    if (jassubWorkerBlobUrl) return jassubWorkerBlobUrl;
    if (jassubWorkerPromise) return jassubWorkerPromise;
    jassubWorkerPromise = (async () => {
      try {
        const res = await fetch('https://cdn.jsdelivr.net/npm/jassub/dist/jassub-worker.js');
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const code = await res.text();
        const blob = new Blob([code], { type: 'application/javascript' });
        jassubWorkerBlobUrl = URL.createObjectURL(blob);
        return jassubWorkerBlobUrl;
      } catch (err) {
        console.warn('[JASSUB] Worker blob fallback:', err);
        return 'https://cdn.jsdelivr.net/npm/jassub/dist/jassub-worker.js';
      }
    })();
    return jassubWorkerPromise;
  }

  // MoviJassubSubtitleRenderer class
  class MoviJassubSubtitleRenderer {
    constructor() {
      this.jassub = null;
      this.overlay = null;
      this.canvas = null;
      this.delay = 0;
      this.activeTrack = null;
      this.decoder = new TextDecoder('utf-8');
      this.seenPackets = new Set();
      this.readOrder = 0;
      this.pendingPackets = [];
      this.initPromise = null;
      this.currentRenderW = 0;
      this.currentRenderH = 0;
    }

    mount(overlay) {
      this.overlay = overlay;
      const parent = moviPlayer?.shadowRoot || (overlay && overlay.parentNode) || playerCanvas;
      if (!this.canvas) {
        this.canvas = document.createElement('canvas');
        this.canvas.className = 'jassub-subtitle-canvas';
        this.canvas.style.position = 'absolute';
        this.canvas.style.top = '0';
        this.canvas.style.left = '0';
        this.canvas.style.width = '100%';
        this.canvas.style.height = '100%';
        this.canvas.style.pointerEvents = 'none';
        this.canvas.style.zIndex = '10';
        this.canvas.style.display = 'block';
        this.canvas.style.transformOrigin = 'bottom center';
        if (this.scale && this.scale !== 1.0) {
          this.canvas.style.transform = `scale(${this.scale})`;
        }
        this.canvas.width = 1920;
        this.canvas.height = 1080;
        this.currentRenderW = 1920;
        this.currentRenderH = 1080;
      }
      if (parent && this.canvas.parentNode !== parent) {
        parent.appendChild(this.canvas);
      }
    }

    setScale(scale) {
      this.scale = scale || 1.0;
      if (this.canvas) {
        this.canvas.style.transformOrigin = 'bottom center';
        this.canvas.style.transform = this.scale !== 1.0 ? `scale(${this.scale})` : '';
      }
    }

    async configure(track, extradata) {
      this.activeTrack = track;
      this.seenPackets.clear();
      this.readOrder = 0;

      const codec = (track?.codec || '').toLowerCase();
      if (!codec.includes('ass') && !codec.includes('ssa')) {
        if (this.canvas) this.canvas.style.display = 'none';
        return;
      }

      if (this.canvas) this.canvas.style.display = 'block';

      let headerText = '';
      if (extradata && extradata.length > 0) {
        headerText = this.decoder.decode(extradata);
      } else {
        headerText = '[Script Info]\nTitle: Subtitles\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,Arial,24,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n';
      }

      if (!headerText.includes('[Events]')) {
        headerText += '\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n';
      }

      if (this.initPromise) {
        try { await this.initPromise; } catch (_) {}
      }

      if (!this.jassub && window.JASSUB && this.canvas) {
        this.initPromise = (async () => {
          const defaultFontUrl = 'https://cdn.jsdelivr.net/npm/jassub/dist/default.woff2';
          const workerUrl = await getJassubWorkerUrl();

          const vTrack = moviPlayer?.player?.trackManager?.getActiveVideoTrack?.();
          const vW = vTrack?.width || 1920;
          const vH = vTrack?.height || 1080;
          const dpr = Math.min(window.devicePixelRatio || 1, 2);
          const rect = moviPlayer?.getBoundingClientRect() || { width: vW, height: vH };
          const dispW = Math.round(rect.width) || vW;
          const dispH = Math.round(rect.height) || vH;

          const targetW = Math.min(3840, Math.max(vW, Math.round(dispW * dpr)));
          const targetH = Math.min(2160, Math.max(vH, Math.round(dispH * dpr)));

          this.canvas.width = targetW;
          this.canvas.height = targetH;
          this.currentRenderW = targetW;
          this.currentRenderH = targetH;

          this.jassub = new window.JASSUB({
            canvas: this.canvas,
            subContent: headerText,
            workerUrl: workerUrl,
            wasmUrl: 'https://cdn.jsdelivr.net/npm/jassub/dist/jassub-worker.wasm',
            modernWasmUrl: 'https://cdn.jsdelivr.net/npm/jassub/dist/jassub-worker-modern.wasm',
            legacyWasmUrl: 'https://cdn.jsdelivr.net/npm/jassub/dist/jassub-worker.wasm.js',
            fonts: [defaultFontUrl],
            availableFonts: {
              'liberation sans': defaultFontUrl,
              'default': defaultFontUrl,
              'arial': defaultFontUrl,
              'sans-serif': defaultFontUrl,
              'trebuchet ms': defaultFontUrl,
              'dejavu sans': defaultFontUrl,
              'tahoma': defaultFontUrl,
              'verdana': defaultFontUrl
            },
            fallbackFont: 'liberation sans',
            useLocalFonts: false,
            onDemandRender: false,
            useSimd: true
          });
          this.jassub._video = { videoWidth: vW, videoHeight: vH };
          this.jassub._videoWidth = vW;
          this.jassub._videoHeight = vH;

          if (this.pendingPackets.length > 0) {
            const queued = this.pendingPackets.slice();
            this.pendingPackets = [];
            for (const pkt of queued) {
              this.pushPacket(pkt);
            }
          }
        })();

        try {
          await this.initPromise;
        } catch (e) {
          console.error('[JASSUB] Engine init error:', e);
        } finally {
          this.initPromise = null;
        }
      } else if (this.jassub) {
        try {
          this.jassub.setTrack(headerText);
        } catch (e) {
          console.warn('[JASSUB] setTrack error:', e);
        }
      }
    }

    pushPacket(pkt) {
      if (!pkt || !pkt.data) return;
      if (!this.jassub) {
        this.pendingPackets.push(pkt);
        return;
      }
      try {
        const raw = this.decoder.decode(pkt.data).trim();
        if (!raw) return;

        let startMs = Math.round(((pkt.timestamp || 0) + this.delay) * 1000);
        let durationMs = Math.round((pkt.duration && pkt.duration > 0 ? pkt.duration : 5) * 1000);

        let layer = 0, style = 'Default', name = '', marginL = 0, marginR = 0, marginV = 0, effect = '', text = '';
        let readOrder = ++this.readOrder;

        if (raw.startsWith('Dialogue:')) {
          const parts = raw.substring(9).trim().split(',');
          if (parts.length >= 9) {
            layer = parseInt(parts[0], 10) || 0;
            style = parts[3] || 'Default';
            name = parts[4] || '';
            marginL = parseInt(parts[5], 10) || 0;
            marginR = parseInt(parts[6], 10) || 0;
            marginV = parseInt(parts[7], 10) || 0;
            effect = parts[8] || '';
            text = parts.slice(9).join(',');
          } else {
            text = raw;
          }
        } else {
          const parts = raw.split(',');
          if (parts.length >= 9) {
            readOrder = parseInt(parts[0], 10) || readOrder;
            layer = parseInt(parts[1], 10) || 0;
            style = parts[2] || 'Default';
            name = parts[3] || '';
            marginL = parseInt(parts[4], 10) || 0;
            marginR = parseInt(parts[5], 10) || 0;
            marginV = parseInt(parts[6], 10) || 0;
            effect = parts[7] || '';
            text = parts.slice(8).join(',');
          } else {
            text = raw;
          }
        }

        const dedupKey = startMs + '_' + text;
        if (this.seenPackets.has(dedupKey)) return;
        this.seenPackets.add(dedupKey);

        this.jassub.createEvent({
          Start: startMs,
          Duration: durationMs,
          ReadOrder: readOrder,
          Layer: layer,
          Style: style,
          Name: name,
          MarginL: marginL,
          MarginR: marginR,
          MarginV: marginV,
          Effect: effect,
          Text: text
        });
      } catch (e) {
        console.warn('[JASSUB] Packet error:', e);
      }
    }

    render(currentTime, videoWidth, videoHeight) {
      if (!this.jassub || !this.canvas) return;
      try {
        const isPaused = !!moviPlayer?.paused;
        const rate = moviPlayer?.playbackRate || 1;
        this.jassub.setCurrentTime(isPaused, currentTime + this.delay, rate);

        const host = moviPlayer?.shadowRoot || (this.overlay && this.overlay.parentNode) || playerCanvas;
        if (host && this.canvas.parentNode !== host) {
          host.appendChild(this.canvas);
        }

        const vW = videoWidth || 1920;
        const vH = videoHeight || 1080;
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        const rect = moviPlayer?.getBoundingClientRect() || { width: vW, height: vH };
        const dispW = Math.round(rect.width) || vW;
        const dispH = Math.round(rect.height) || vH;

        const targetW = Math.min(3840, Math.max(vW, Math.round(dispW * dpr)));
        const targetH = Math.min(2160, Math.max(vH, Math.round(dispH * dpr)));

        if (this.currentRenderW !== targetW || this.currentRenderH !== targetH) {
          this.currentRenderW = targetW;
          this.currentRenderH = targetH;
          if (!this.jassub._video) {
            this.jassub._video = { videoWidth: vW, videoHeight: vH };
          } else {
            this.jassub._video.videoWidth = vW;
            this.jassub._video.videoHeight = vH;
          }
          this.jassub._videoWidth = vW;
          this.jassub._videoHeight = vH;
          if (typeof this.jassub.resize === 'function') {
            this.jassub.resize(targetW, targetH, 0, 0, isPaused);
          }
        }
      } catch (e) {
        console.warn('[JASSUB] render error:', e);
      }
    }

    setDelay(delaySec) {
      this.delay = delaySec || 0;
    }

    clear() {
      if (this.canvas) {
        const ctx = this.canvas.getContext('2d');
        if (ctx) ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
      }
    }

    destroy() {
      this.pendingPackets = [];
      this.initPromise = null;
      this.currentRenderW = 0;
      this.currentRenderH = 0;
      if (this.jassub) {
        try { this.jassub.destroy(); } catch (_) {}
        this.jassub = null;
      }
      if (this.canvas && this.canvas.parentNode) {
        this.canvas.parentNode.removeChild(this.canvas);
        this.canvas = null;
      }
    }
  }

  let assRenderer = null;
  let lastAttachedTrackId = null;

  function syncSubtitleRenderer() {
    if (!window.JASSUB || !moviPlayer) return;
    try {
      const inner = moviPlayer.player;
      if (!inner) return;
      const track = inner.trackManager?.getActiveSubtitleTrack?.();
      if (!track) {
        if (assRenderer) {
          moviPlayer.setSubtitleRenderer(null);
          lastAttachedTrackId = null;
        }
        return;
      }
      const codec = (track.codec || '').toLowerCase();
      const isAss = codec.includes('ass') || codec.includes('ssa');
      if (isAss) {
        if (lastAttachedTrackId === track.id && moviPlayer.player?._customSubtitleRenderer === assRenderer) {
          return;
        }
        if (!assRenderer) {
          assRenderer = new MoviJassubSubtitleRenderer();
        }
        moviPlayer.setSubtitleRenderer(assRenderer);
        lastAttachedTrackId = track.id;
      } else {
        if (assRenderer) {
          moviPlayer.setSubtitleRenderer(null);
          lastAttachedTrackId = null;
        }
      }
    } catch (e) {
      console.warn('[Subtitle] syncSubtitleRenderer error:', e);
    }
  }

  // Audio Context Unlocking for Autoplay Policy
  function unlockAudio() {
    try {
      const renderer = moviPlayer?.player?.audioRenderer;
      if (renderer?.audioContext && renderer.audioContext.state === 'suspended') {
        renderer.audioContext.resume().catch(() => {});
      }
      if (moviPlayer?.player?.audioContext && moviPlayer.player.audioContext.state === 'suspended') {
        moviPlayer.player.audioContext.resume().catch(() => {});
      }
      if (moviPlayer?.shadowRoot) {
        const overlay = moviPlayer.shadowRoot.querySelector('.movi-unmute-overlay');
        if (overlay && overlay.style.display !== 'none') {
          overlay.click();
        }
      }
      if (moviPlayer) {
        moviPlayer._userHasUnmuted = true;
        moviPlayer._autoMutedForAutoplay = false;
        moviPlayer.muted = false;
        moviPlayer.volume = 1;
        moviPlayer.removeAttribute('muted');
        if (moviPlayer.player) {
          if (typeof moviPlayer.player.setMuted === 'function') moviPlayer.player.setMuted(false);
          if (typeof moviPlayer.player.setVolume === 'function') moviPlayer.player.setVolume(1);
        }
        if (typeof moviPlayer.updateVolume === 'function') moviPlayer.updateVolume();
      }
    } catch (_) {}
  }

  window.addEventListener('click', unlockAudio, { capture: true });
  window.addEventListener('touchstart', unlockAudio, { capture: true, passive: true });
  window.addEventListener('pointerdown', unlockAudio, { capture: true, passive: true });
  window.addEventListener('keydown', unlockAudio, { capture: true, passive: true });

  let subtitleSelected = false;
  function autoSelectSubtitle() {
    if (subtitleSelected || !moviPlayer) return;
    try {
      const inner = moviPlayer.player;
      if (inner) {
        const activeTrack = inner.trackManager?.getActiveSubtitleTrack?.();
        if (activeTrack) {
          subtitleSelected = true;
          activeSubTrackId = activeTrack.id;
          return;
        }
        const tracks = typeof inner.getSubtitleTracks === 'function' ? inner.getSubtitleTracks() : [];
        if (tracks && tracks.length > 0) {
          let target = tracks.find((t) => {
            const l = (t.language || t.lang || '').toLowerCase();
            const b = (t.label || '').toLowerCase();
            const isDef = !!(t.default || t.isDefault);
            return isDef && (l === 'eng' || l.startsWith('en') || b.includes('eng') || b.includes('english'));
          });
          if (!target) target = tracks.find((t) => !!(t.default || t.isDefault));
          if (!target) {
            target = tracks.find((t) => {
              const l = (t.language || t.lang || '').toLowerCase();
              const b = (t.label || '').toLowerCase();
              return l === 'eng' || l.startsWith('en') || b.includes('eng') || b.includes('english');
            });
          }
          if (!target) target = tracks[0];

          if (target && target.id !== undefined) {
            if (typeof moviPlayer.pickSubtitleTrack === 'function') {
              moviPlayer.pickSubtitleTrack(target.id);
            } else if (typeof inner.selectSubtitleTrack === 'function') {
              inner.selectSubtitleTrack(target.id);
            }
            subtitleSelected = true;
            activeSubTrackId = target.id;
            return;
          }
        }
      }
    } catch (_) {}
  }

  // Fallback timer and player loader
  let fallbackTimeoutTimer = null;
  let playerReady = false;

  function dismissPlayerLoading() {
    playerReady = true;
    playerLoadingSpinner.classList.remove('visible');
    playerErrorOverlay.classList.remove('visible');
    if (fallbackTimeoutTimer) {
      clearTimeout(fallbackTimeoutTimer);
      fallbackTimeoutTimer = null;
    }
  }

  async function loadVideoSource(file) {
    hasResumedCurrentVideo = false;
    subtitleSelected = false;
    playerReady = false;
    activeSubTrackId = null;
    playerErrorOverlay.classList.remove('visible');
    playerLoadingSpinner.classList.add('visible');

    // Clear subtitle language preferences so MKV defaults are not suppressed
    try {
      localStorage.removeItem('movi-player-subtitlelang');
      localStorage.removeItem('movi:subtitlelang');
      sessionStorage.removeItem('movi-player-subtitlelang');
      sessionStorage.removeItem('movi:subtitlelang');
    } catch (_) {}

    await ensureMoviPlayerReady();

    // Reset display
    if (moviPlayer) {
      moviPlayer.style.display = 'block';
      moviPlayer.volume = 1;
      moviPlayer.muted = false;
      try { moviPlayer.removeAttribute('muted'); } catch (_) {}
      if (moviPlayer.getAttribute('src') !== file.stream_url) {
        moviPlayer.setAttribute('src', file.stream_url);
        moviPlayer.src = file.stream_url;
      }
      try {
        if (typeof moviPlayer.play === 'function') {
          moviPlayer.play().catch(() => {});
        }
      } catch (_) {}
    }
    if (nativeFallback) {
      nativeFallback.style.display = 'none';
      try { nativeFallback.pause(); } catch (_) {}
      nativeFallback.src = '';
    }

    if (fallbackTimeoutTimer) clearTimeout(fallbackTimeoutTimer);
    fallbackTimeoutTimer = setTimeout(() => {
      const isActivelyPlaying = moviPlayer && (!moviPlayer.paused || moviPlayer.currentTime > 0);
      if (playerReady || isActivelyPlaying) {
        dismissPlayerLoading();
        return;
      }
      dismissPlayerLoading();
      const hasInit = moviPlayer && (moviPlayer.shadowRoot || moviPlayer.player);
      if (!hasInit) {
        console.warn('[Player] Movi WASM element timeout after 30s');
        if (file && file.name && file.name.match(/\.(mp4|webm)$/i)) {
          activateNativeFallback(file);
        } else {
          if (!isActivelyPlaying) {
            playerErrorOverlay.classList.add('visible');
          }
        }
      }
    }, 30000);
  }

  function activateNativeFallback(file) {
    if (moviPlayer) {
      try { moviPlayer.pause(); } catch (_) {}
      moviPlayer.style.display = 'none';
    }
    if (nativeFallback) {
      nativeFallback.style.display = 'block';
      nativeFallback.src = file.stream_url;
      nativeFallback.play().then(() => {
        dismissPlayerLoading();
      }).catch(() => {
        dismissPlayerLoading();
      });
    }
  }

  function loadNativeSubtitleTrack(subIndex, label) {
    if (!nativeFallback || !currentActiveFile) return;
    nativeFallback.querySelectorAll('track').forEach((t) => t.remove());
    if (subIndex === null || subIndex === -1) {
      if (nativeFallback.textTracks) {
        for (let j = 0; j < nativeFallback.textTracks.length; j++) {
          nativeFallback.textTracks[j].mode = 'disabled';
        }
      }
      return;
    }
    const tr = document.createElement('track');
    tr.kind = 'subtitles';
    tr.label = label || 'Subtitles';
    tr.srclang = 'en';
    tr.src = `/api/media/${currentActiveFile.display_id || currentActiveFile.id}/subs/${subIndex}.vtt`;
    tr.default = true;
    tr.onload = () => {
      try {
        if (tr.track) tr.track.mode = 'showing';
      } catch (_) {}
    };
    nativeFallback.appendChild(tr);
  }

  // Player Event Listeners
  if (moviPlayer) {
    moviPlayer.addEventListener('loadeddata', () => {
      dismissPlayerLoading();
      unlockAudio();
      autoSelectSubtitle();
      syncSubtitleRenderer();
      applySubtitleCustomization(activeSubSize);
      if (currentActiveFile) checkAndResumeProgress(currentActiveFile);
    });

    moviPlayer.addEventListener('canplay', () => {
      dismissPlayerLoading();
      unlockAudio();
      autoSelectSubtitle();
      if (currentActiveFile) checkAndResumeProgress(currentActiveFile);
    });

    moviPlayer.addEventListener('playing', () => {
      dismissPlayerLoading();
      unlockAudio();
      autoSelectSubtitle();
      applySubtitleCustomization(activeSubSize);
      if (currentActiveFile) checkAndResumeProgress(currentActiveFile);
    });

    moviPlayer.addEventListener('waiting', () => {
      playerLoadingSpinner.classList.add('visible');
    });

    moviPlayer.addEventListener('timeupdate', () => {
      dismissPlayerLoading();
      if (currentActiveFile && !hasResumedCurrentVideo) checkAndResumeProgress(currentActiveFile);
      savePlaybackProgress();
    });

    moviPlayer.addEventListener('subtitletrackchange', () => {
      const active = moviPlayer.player?.trackManager?.getActiveSubtitleTrack?.();
      if (active) {
        subtitleSelected = true;
        activeSubTrackId = active.id;
      }
      syncSubtitleRenderer();
    });

    moviPlayer.addEventListener('error', (e) => {
      console.warn('[MoviPlayer] Error event:', e);
      // If audio or video has already started or is actively progressing, ignore non-fatal warnings
      if (moviPlayer && (moviPlayer.currentTime > 0 || !moviPlayer.paused)) {
        return;
      }
      dismissPlayerLoading();
      // If error occurred on mp4/webm, try native fallback. Otherwise let Movi retry
      if (currentActiveFile && currentActiveFile.name && currentActiveFile.name.match(/\.(mp4|webm)$/i)) {
        activateNativeFallback(currentActiveFile);
      }
    });

    moviPlayer.addEventListener('ended', () => {
      if (currentActiveFile) {
        const key = getFileProgressKey(currentActiveFile);
        if (key) {
          try { localStorage.removeItem(key); } catch (_) {}
        }
      }
    });
  }

  if (nativeFallback) {
    nativeFallback.addEventListener('loadeddata', dismissPlayerLoading);
    nativeFallback.addEventListener('canplay', () => {
      dismissPlayerLoading();
      if (currentActiveFile) checkAndResumeProgress(currentActiveFile);
    });
    nativeFallback.addEventListener('timeupdate', savePlaybackProgress);
    nativeFallback.addEventListener('error', (e) => {
      if (nativeFallback.style.display === 'none' || !nativeFallback.src) return;
      console.warn('[NativeFallback] Error event:', e);
      playerLoadingSpinner.classList.remove('visible');
      playerErrorOverlay.classList.add('visible');
    });
  }

  // Periodic check for MKV subtitle detection during first 8 seconds
  const subCheckInterval = setInterval(() => {
    if (viewPlayer.classList.contains('active')) {
      autoSelectSubtitle();
      syncSubtitleRenderer();
    }
  }, 350);
  setTimeout(() => clearInterval(subCheckInterval), 8500);

  // Keyboard Shortcuts (Desktop)
  document.addEventListener('keydown', (e) => {
    if (viewPlayer.classList.contains('active') && !trackSheetContainer.classList.contains('active')) {
      const activeEl = (moviPlayer && moviPlayer.style.display !== 'none') ? moviPlayer : nativeFallback;
      if (!activeEl) return;

      if (e.code === 'Escape' && isFullscreenActive()) {
        exitFullscreenMode();
        return;
      }

      if (e.code === 'Space') {
        e.preventDefault();
        if (activeEl.paused) {
          activeEl.play().catch(() => {});
        } else {
          activeEl.pause();
        }
      } else if (e.code === 'ArrowLeft') {
        const step = (typeof activeSeekDuration === 'number' && activeSeekDuration > 0) ? activeSeekDuration : 10;
        activeEl.currentTime = Math.max(0, activeEl.currentTime - step);
      } else if (e.code === 'ArrowRight') {
        const step = (typeof activeSeekDuration === 'number' && activeSeekDuration > 0) ? activeSeekDuration : 10;
        activeEl.currentTime = Math.min(activeEl.duration || Infinity, activeEl.currentTime + step);
      }
    }
  });

  // ==============================================================================
  // FULLSCREEN MANAGEMENT (Native API + CSS Pseudo-Fullscreen for Mobile/Telegram)
  // ==============================================================================

  function isFullscreenActive() {
    return !!(document.fullscreenElement || document.webkitFullscreenElement || document.body.classList.contains('is-fullscreen'));
  }

  function toggleFullscreen() {
    if (isFullscreenActive()) {
      exitFullscreenMode();
    } else {
      enterFullscreenMode();
    }
  }

  function enterFullscreenMode() {
    const elem = playerCanvas;
    if (!elem) return;

    // Inside Telegram WebApp:
    const isInsideTelegram = !!(window.Telegram?.WebApp?.initData);
    if (isInsideTelegram) {
      if (tg?.expand) {
        try { tg.expand(); } catch (_) {}
      }
      if (tg && typeof tg.requestFullscreen === 'function') {
        try { tg.requestFullscreen(); } catch (_) {}
      }
      // Use clean CSS pseudo-fullscreen takeover inside Telegram
      fallbackPseudoFullscreen();
      return;
    }

    // In regular external browser (Chrome / Edge / Firefox):
    if (elem.requestFullscreen) {
      elem.requestFullscreen().then(() => {
        document.documentElement.classList.add('is-fullscreen');
        document.body.classList.add('is-fullscreen');
        triggerHaptic('medium');
      }).catch(() => {
        fallbackPseudoFullscreen();
      });
    } else if (elem.webkitRequestFullscreen) {
      elem.webkitRequestFullscreen();
      document.documentElement.classList.add('is-fullscreen');
      document.body.classList.add('is-fullscreen');
      triggerHaptic('medium');
    } else {
      fallbackPseudoFullscreen();
    }

    try {
      if (screen.orientation && typeof screen.orientation.lock === 'function') {
        screen.orientation.lock('landscape').catch(() => {});
      }
    } catch (_) {}
  }

  function fallbackPseudoFullscreen() {
    document.documentElement.classList.add('is-fullscreen');
    document.body.classList.add('is-fullscreen', 'css-pseudo-fs');
    try {
      if (screen.orientation && typeof screen.orientation.lock === 'function') {
        screen.orientation.lock('landscape').catch(() => {});
      }
    } catch (_) {}
    triggerHaptic('medium');
  }

  function exitFullscreenMode() {
    if (tg && typeof tg.exitFullscreen === 'function') {
      try { tg.exitFullscreen(); } catch (_) {}
    }
    if (document.exitFullscreen) {
      document.exitFullscreen().catch(() => {});
    } else if (document.webkitExitFullscreen) {
      document.webkitExitFullscreen();
    }
    document.documentElement.classList.remove('is-fullscreen');
    document.body.classList.remove('is-fullscreen', 'css-pseudo-fs');
    try {
      if (screen.orientation && typeof screen.orientation.unlock === 'function') {
        screen.orientation.unlock();
      }
    } catch (_) {}
    triggerHaptic('light');
  }

  function openInWebBrowser(file) {
    if (!file) return;
    const playerEl = (moviPlayer && moviPlayer.style.display !== 'none') ? moviPlayer : nativeFallback;
    let curTime = Math.floor(playerEl?.currentTime || 0);

    // If stream hasn't started yet in WebApp, grab latest saved progress from storage
    if (curTime <= 2) {
      const key = getFileProgressKey(file);
      if (key) {
        try {
          const saved = parseFloat(localStorage.getItem(key));
          if (saved && isFinite(saved) && saved > 2) {
            curTime = Math.floor(saved);
          }
        } catch (_) {}
      }
    }

    // Also check if initial file object had resume_time
    if (curTime <= 2 && file.resume_time && isFinite(file.resume_time) && file.resume_time > 2) {
      curTime = Math.floor(file.resume_time);
    }

    const baseWatchUrl = file.watch_url || `${window.location.origin}/watch/${file.display_id || file.id}`;
    const targetUrl = curTime > 2 ? `${baseWatchUrl}?t=${curTime}` : baseWatchUrl;

    savePlaybackProgress();

    if (tg && typeof tg.openLink === 'function') {
      tg.openLink(targetUrl);
    } else {
      window.open(targetUrl, '_blank');
    }
    showToast(curTime > 2 ? `Opening browser from ${formatTime(curTime)}...` : 'Opening in browser...');
    triggerHaptic('medium');
  }

  if (btnExitFullscreen) {
    btnExitFullscreen.addEventListener('click', (e) => {
      e.stopPropagation();
      exitFullscreenMode();
    });
  }

  // Intercept Movi Player internal fullscreen button request
  if (moviPlayer) {
    moviPlayer.addEventListener('movi-fullscreen-request', (e) => {
      e.preventDefault();
      toggleFullscreen();
    });
  }

  // Handle native browser fullscreen change events
  document.addEventListener('fullscreenchange', () => {
    if (!document.fullscreenElement) {
      document.body.classList.remove('is-fullscreen', 'css-pseudo-fs');
    } else {
      document.body.classList.add('is-fullscreen');
    }
  });

  document.addEventListener('webkitfullscreenchange', () => {
    if (!document.webkitFullscreenElement) {
      document.body.classList.remove('is-fullscreen', 'css-pseudo-fs');
    } else {
      document.body.classList.add('is-fullscreen');
    }
  });

  // ==============================================================================
  // AUDIO & SUBTITLE SWITCHER BOTTOM SHEET / MODAL
  // ==============================================================================

  async function probeMediaTracks(identifier) {
    try {
      const res = await fetch(`/api/media/${identifier}/tracks`);
      currentTracksData = await res.json();
    } catch (e) {
      console.warn('[Tracks] Server probe error:', e);
      currentTracksData = { audio: [], subtitles: [] };
    }
  }

  function populateTrackSheetFromMovi() {
    const inner = moviPlayer?.player;
    let audioTracks = [];
    let subTracks = [];
    let currentAudioId = activeAudioIndex || 0;

    if (inner) {
      if (typeof inner.getAudioTracks === 'function') {
        audioTracks = inner.getAudioTracks() || [];
      }
      if (typeof inner.getSubtitleTracks === 'function') {
        subTracks = inner.getSubtitleTracks() || [];
      }
      const activeAudio = inner.trackManager?.getActiveAudioTrack?.();
      if (activeAudio && activeAudio.id !== undefined) currentAudioId = activeAudio.id;
      const activeSub = inner.trackManager?.getActiveSubtitleTrack?.();
      if (activeSub && activeSub.id !== undefined) activeSubTrackId = activeSub.id;
    }

    // Fallback to server probed data if demuxer tracks are not populated yet
    if (audioTracks.length === 0 && currentTracksData?.audio?.length > 0) {
      audioTracks = currentTracksData.audio.map((a, i) => ({
        id: i,
        label: a.language_name || a.title || `Track ${i + 1}`,
        codec: a.codec || 'AAC',
        channels: a.channels === 6 ? '5.1' : 'Stereo'
      }));
    }
    if (subTracks.length === 0 && currentTracksData?.subtitles?.length > 0) {
      subTracks = currentTracksData.subtitles.map((s, i) => ({
        id: s.index !== undefined ? s.index : i,
        label: s.language_name || s.title || `Subtitle ${i + 1}`,
        codec: s.codec || 'ASS'
      }));
    }

    // 1. Render Audio Tracks
    audioTracksList.innerHTML = '';
    if (audioTracks.length === 0) {
      audioTracksList.innerHTML = `
        <div class="track-item-row selected">
          <div class="track-item-left">
            <span class="track-item-name">Default Audio</span>
            <span class="track-item-desc">Original Stereo</span>
          </div>
          <span class="track-check-indicator">✓</span>
        </div>
      `;
    } else {
      audioTracks.forEach((tr, i) => {
        const isSelected = (currentAudioId !== null) ? (tr.id === currentAudioId) : (i === 0);
        const item = document.createElement('div');
        item.className = `track-item-row ${isSelected ? 'selected' : ''}`;
        const name = tr.label || tr.title || tr.language || `Track ${i + 1}`;
        const desc = `${(tr.codec || 'AAC').toUpperCase()} • ${tr.channels ? tr.channels : 'Stereo'}`;

        item.innerHTML = `
          <div class="track-item-left">
            <span class="track-item-name">${escapeHtml(name)}</span>
            <span class="track-item-desc">${escapeHtml(desc)}</span>
          </div>
          <span class="track-check-indicator">✓</span>
        `;

        item.addEventListener('click', () => {
          activeAudioIndex = tr.id !== undefined ? tr.id : i;
          if (moviPlayer) {
            if (typeof moviPlayer.pickAudioTrack === 'function') {
              moviPlayer.pickAudioTrack(activeAudioIndex);
            }
            if (typeof inner?.selectAudioTrack === 'function') {
              inner.selectAudioTrack(activeAudioIndex);
            }
          }
          audioTracksList.querySelectorAll('.track-item-row').forEach((r) => r.classList.remove('selected'));
          item.classList.add('selected');
          showToast(`Audio: ${name}`);
          triggerHaptic('select');
        });

        audioTracksList.appendChild(item);
      });
    }

    // 2. Render Subtitle Tracks (Fix selection & guarantee removal from OFF!)
    subTracksList.innerHTML = '';

    const isOff = (activeSubTrackId === null || activeSubTrackId === -1 || activeSubTrackId === undefined);
    
    // "Off" Button
    const offItem = document.createElement('div');
    offItem.className = `track-item-row ${isOff ? 'selected' : ''}`;
    offItem.innerHTML = `
      <div class="track-item-left">
        <span class="track-item-name">Off</span>
        <span class="track-item-desc">Subtitles Disabled</span>
      </div>
      <span class="track-check-indicator">✓</span>
    `;

    offItem.addEventListener('click', () => {
      activeSubTrackId = null;
      if (moviPlayer) {
        if (typeof moviPlayer.pickSubtitleTrack === 'function') {
          moviPlayer.pickSubtitleTrack(null);
        }
        if (typeof inner?.selectSubtitleTrack === 'function') {
          inner.selectSubtitleTrack(null);
        }
        if (typeof moviPlayer.setSubtitleRenderer === 'function') {
          moviPlayer.setSubtitleRenderer(null);
        }
      }
      if (nativeFallback) {
        loadNativeSubtitleTrack(null, 'Off');
      }

      // Unselect every row, select ONLY offItem
      subTracksList.querySelectorAll('.track-item-row').forEach((r) => r.classList.remove('selected'));
      offItem.classList.add('selected');

      showToast('Subtitles: Off');
      triggerHaptic('select');
    });
    subTracksList.appendChild(offItem);

    subTracks.forEach((sub, i) => {
      const isSelected = (!isOff && (sub.id === activeSubTrackId || (activeSubTrackId === null && i === 0 && !isOff)));
      const item = document.createElement('div');
      item.className = `track-item-row ${isSelected ? 'selected' : ''}`;
      const name = sub.label || sub.title || sub.language || `Subtitle ${i + 1}`;
      const desc = `${(sub.codec || 'ASS').toUpperCase()} • ${sub.isDefault ? 'Default' : 'Embedded'}`;

      item.innerHTML = `
        <div class="track-item-left">
          <span class="track-item-name">${escapeHtml(name)}</span>
          <span class="track-item-desc">${escapeHtml(desc)}</span>
        </div>
        <span class="track-check-indicator">✓</span>
      `;

      item.addEventListener('click', () => {
        const targetId = sub.id !== undefined ? sub.id : i;
        activeSubTrackId = targetId;

        if (moviPlayer) {
          if (typeof moviPlayer.pickSubtitleTrack === 'function') {
            moviPlayer.pickSubtitleTrack(targetId);
          }
          if (typeof inner?.selectSubtitleTrack === 'function') {
            inner.selectSubtitleTrack(targetId);
          }
          syncSubtitleRenderer();
        }
        if (nativeFallback) {
          loadNativeSubtitleTrack(targetId, name);
        }

        // Unselect every row (INCLUDING OFF!), and mark ONLY this row as selected!
        subTracksList.querySelectorAll('.track-item-row').forEach((r) => r.classList.remove('selected'));
        item.classList.add('selected');

        showToast(`Subtitles: ${name}`);
        triggerHaptic('select');
      });

      subTracksList.appendChild(item);
    });

    openTrackSheet();
  }

  // Open / Close Track Sheet
  function openTrackSheet() {
    trackModalBackdrop.classList.add('active');
    trackSheetContainer.classList.add('active');
    triggerHaptic('light');
  }

  function closeTrackSheet() {
    trackModalBackdrop.classList.remove('active');
    trackSheetContainer.classList.remove('active');
  }

  btnCloseTrackSheet.addEventListener('click', closeTrackSheet);
  trackModalBackdrop.addEventListener('click', closeTrackSheet);

  // Tab switching inside bottom sheet
  tabBtnAudio.addEventListener('click', () => {
    tabBtnAudio.classList.add('active');
    tabBtnSubs.classList.remove('active');
    trackSectionAudio.classList.add('active');
    trackSectionSubs.classList.remove('active');
    triggerHaptic('select');
  });

  tabBtnSubs.addEventListener('click', () => {
    tabBtnSubs.classList.add('active');
    tabBtnAudio.classList.remove('active');
    trackSectionSubs.classList.add('active');
    trackSectionAudio.classList.remove('active');
    triggerHaptic('select');
  });

  // ==============================================================================
  // DASHBOARD SEGMENTED TABS (MY FILES vs PREFERENCES)
  // ==============================================================================

  function switchDashboardTab(targetTab) {
    if (!tabDashFiles || !tabDashSettings) return;

    if (targetTab === 'files') {
      tabDashFiles.classList.add('active');
      tabDashFiles.setAttribute('aria-selected', 'true');
      tabDashFiles.setAttribute('tabindex', '0');

      tabDashSettings.classList.remove('active');
      tabDashSettings.setAttribute('aria-selected', 'false');
      tabDashSettings.setAttribute('tabindex', '-1');

      if (dashContentFiles) {
        dashContentFiles.classList.add('active');
        dashContentFiles.style.display = 'block';
      }
      if (dashContentSettings) {
        dashContentSettings.classList.remove('active');
        dashContentSettings.style.display = 'none';
      }
    } else if (targetTab === 'settings') {
      tabDashSettings.classList.add('active');
      tabDashSettings.setAttribute('aria-selected', 'true');
      tabDashSettings.setAttribute('tabindex', '0');

      tabDashFiles.classList.remove('active');
      tabDashFiles.setAttribute('aria-selected', 'false');
      tabDashFiles.setAttribute('tabindex', '-1');

      if (dashContentSettings) {
        dashContentSettings.classList.add('active');
        dashContentSettings.style.display = 'block';
      }
      if (dashContentFiles) {
        dashContentFiles.classList.remove('active');
        dashContentFiles.style.display = 'none';
      }
    }
    triggerHaptic('select');
  }

  if (tabDashFiles && tabDashSettings) {
    tabDashFiles.addEventListener('click', () => switchDashboardTab('files'));
    tabDashSettings.addEventListener('click', () => switchDashboardTab('settings'));

    // Keyboard accessibility for tab list
    [tabDashFiles, tabDashSettings].forEach((tabBtn) => {
      tabBtn.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
          e.preventDefault();
          if (tabBtn === tabDashFiles) {
            tabDashSettings.focus();
            switchDashboardTab('settings');
          } else {
            tabDashFiles.focus();
            switchDashboardTab('files');
          }
        } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
          e.preventDefault();
          if (tabBtn === tabDashSettings) {
            tabDashFiles.focus();
            switchDashboardTab('files');
          } else {
            tabDashSettings.focus();
            switchDashboardTab('settings');
          }
        }
      });
    });

    // Ensure initial display states match on load
    if (dashContentFiles) dashContentFiles.style.display = 'block';
    if (dashContentSettings) dashContentSettings.style.display = 'none';
  }

  // ==============================================================================
  // DASHBOARD PREFERENCES & SUBTITLE CUSTOMIZATION
  // ==============================================================================

  function applySubtitleCustomization(size, color, bg) {
    if (size) activeSubSize = size;
    if (color) activeSubColor = color;
    if (bg) activeSubBg = bg;

    localStorage.setItem('kayi_sub_size', activeSubSize);
    localStorage.setItem('kayi_sub_color', activeSubColor);
    localStorage.setItem('kayi_sub_bg', activeSubBg);

    let px = '18px';
    let jassubScale = 1.0;
    if (activeSubSize === 'small') { px = '14px'; jassubScale = 0.78; }
    else if (activeSubSize === 'large') { px = '25px'; jassubScale = 1.38; }
    else { px = '18px'; jassubScale = 1.0; }

    let bgStyle = 'transparent';
    let shadowStyle = '0 0 4px #000, -1.5px -1.5px 0 #000, 1.5px -1.5px 0 #000, -1.5px 1.5px 0 #000, 1.5px 1.5px 0 #000, 0 2px 5px rgba(0,0,0,0.9)';
    let padStyle = '0';
    let radiusStyle = '0';

    if (activeSubBg === 'translucent') {
      bgStyle = 'rgba(0, 0, 0, 0.72)';
      shadowStyle = '0 1px 3px rgba(0,0,0,0.8)';
      padStyle = '3px 8px';
      radiusStyle = '4px';
    } else if (activeSubBg === 'solid') {
      bgStyle = '#000000';
      shadowStyle = 'none';
      padStyle = '3px 8px';
      radiusStyle = '4px';
    }

    // Set root CSS variables for global cues
    document.documentElement.style.setProperty('--sub-font-size', px);
    document.documentElement.style.setProperty('--sub-color', activeSubColor);
    document.documentElement.style.setProperty('--sub-bg', bgStyle);
    document.documentElement.style.setProperty('--sub-shadow', shadowStyle);

    // Update Live Preview on Dashboard
    if (dashSubPreviewText) {
      dashSubPreviewText.style.fontSize = px;
      dashSubPreviewText.style.color = activeSubColor;
      dashSubPreviewText.style.background = bgStyle;
      dashSubPreviewText.style.textShadow = shadowStyle;
      dashSubPreviewText.style.padding = padStyle;
      dashSubPreviewText.style.borderRadius = radiusStyle;
    }
    if (subPreviewText) {
      subPreviewText.style.fontSize = px;
      subPreviewText.style.color = activeSubColor;
    }

    // Apply to movi-player and inject into shadowRoot
    if (moviPlayer) {
      moviPlayer.style.setProperty('--sub-font-size', px);
      moviPlayer.style.setProperty('--movi-sub-font-size', px);
      moviPlayer.style.setProperty('--movi-subtitle-font-size', px);

      if (moviPlayer.shadowRoot) {
        let customStyle = moviPlayer.shadowRoot.getElementById('kayi-sub-custom-style');
        if (!customStyle) {
          customStyle = document.createElement('style');
          customStyle.id = 'kayi-sub-custom-style';
          moviPlayer.shadowRoot.appendChild(customStyle);
        }
        customStyle.textContent = `
          ::part(subtitle), [part*="subtitle"], [part*="sub"], .movi-subtitle, .subtitle, .subtitles-container, .subtitles-container * {
            font-size: ${px} !important;
            color: ${activeSubColor} !important;
            background: ${bgStyle} !important;
            text-shadow: ${shadowStyle} !important;
            padding: ${padStyle} !important;
            border-radius: ${radiusStyle} !important;
            line-height: 1.35 !important;
          }
        `;
      }
    }

    if (nativeFallback) {
      nativeFallback.style.setProperty('--sub-font-size', px);
      nativeFallback.style.setProperty('--sub-color', activeSubColor);
      nativeFallback.style.setProperty('--sub-bg', bgStyle);
    }

    if (assRenderer) {
      assRenderer.setScale?.(jassubScale);
    }
  }

  // Helper to sync pill group active & aria-checked state
  function setPillActive(groupSelector, activePill) {
    document.querySelectorAll(groupSelector).forEach((p) => {
      p.classList.remove('active');
      p.setAttribute('aria-checked', 'false');
    });
    if (activePill) {
      activePill.classList.add('active');
      activePill.setAttribute('aria-checked', 'true');
    }
  }

  // Subtitle size pills
  document.querySelectorAll('.sub-size-pill').forEach((pill) => {
    pill.addEventListener('click', () => {
      setPillActive('.sub-size-pill', pill);
      applySubtitleCustomization(pill.dataset.size, null, null);
      triggerHaptic('light');
    });
  });

  // Subtitle color pills
  document.querySelectorAll('.sub-color-pill').forEach((pill) => {
    pill.addEventListener('click', () => {
      setPillActive('.sub-color-pill', pill);
      applySubtitleCustomization(null, pill.dataset.color, null);
      triggerHaptic('light');
    });
  });

  // Subtitle backdrop pills
  document.querySelectorAll('.sub-bg-pill').forEach((pill) => {
    pill.addEventListener('click', () => {
      setPillActive('.sub-bg-pill', pill);
      applySubtitleCustomization(null, null, pill.dataset.bg);
      triggerHaptic('light');
    });
  });

  // Auto-resume preference toggle
  if (prefAutoResume) {
    const savedAutoResume = localStorage.getItem('kayi_auto_resume') !== 'false';
    prefAutoResume.checked = savedAutoResume;
    prefAutoResume.addEventListener('change', () => {
      localStorage.setItem('kayi_auto_resume', prefAutoResume.checked ? 'true' : 'false');
      triggerHaptic('light');
      showToast(prefAutoResume.checked ? 'Auto-resume enabled' : 'Auto-resume disabled');
    });
  }

  // Seek skip duration pills
  document.querySelectorAll('.sub-seek-pill').forEach((pill) => {
    pill.addEventListener('click', () => {
      setPillActive('.sub-seek-pill', pill);
      activeSeekDuration = parseInt(pill.dataset.seek || '10', 10);
      localStorage.setItem('kayi_seek_duration', activeSeekDuration);
      triggerHaptic('light');
      showToast(`Seek interval set to ${activeSeekDuration}s`);
    });
  });

  // Sync preference UI buttons with saved state on startup
  function initPreferencePills() {
    const sizePill = document.querySelector(`.sub-size-pill[data-size="${activeSubSize}"]`);
    if (sizePill) setPillActive('.sub-size-pill', sizePill);

    const colorPill = document.querySelector(`.sub-color-pill[data-color="${activeSubColor}"]`);
    if (colorPill) setPillActive('.sub-color-pill', colorPill);

    const bgPill = document.querySelector(`.sub-bg-pill[data-bg="${activeSubBg}"]`);
    if (bgPill) setPillActive('.sub-bg-pill', bgPill);

    const seekPill = document.querySelector(`.sub-seek-pill[data-seek="${activeSeekDuration}"]`);
    if (seekPill) setPillActive('.sub-seek-pill', seekPill);

    applySubtitleCustomization(activeSubSize, activeSubColor, activeSubBg);
  }
  initPreferencePills();

  // ==============================================================================
  // EXTERNAL PLAYERS (VLC, MX Player)
  // ==============================================================================

  function openExternalVlc(streamUrl) {
    const isAndroid = /Android/i.test(navigator.userAgent);
    const isIOS = /iPhone|iPad|iPod/i.test(navigator.userAgent);

    if (isAndroid) {
      // Direct Android Intent launches VLC Player
      const androidIntent = `intent:${streamUrl}#Intent;package=org.videolan.vlc;type=video/*;end`;
      window.location.href = androidIntent;
    } else if (isIOS) {
      // iOS VLC custom scheme
      const vlcScheme = `vlc-x-callback://x-callback-url/stream?url=${encodeURIComponent(streamUrl)}`;
      window.location.href = vlcScheme;
    } else {
      // Desktop / General
      const clean = streamUrl.replace('https://', '').replace('http://', '');
      window.location.href = `vlc://${clean}`;
    }

    copyToClipboard(streamUrl);
    showToast('Opening VLC Player (Link copied to clipboard)');
  }

  function openExternalMxPlayer(streamUrl) {
    const androidIntent = `intent:${streamUrl}#Intent;package=com.mxtech.videoplayer.ad;type=video/*;end`;
    window.location.href = androidIntent;
    copyToClipboard(streamUrl);
    showToast('Opening MX Player (Link copied to clipboard)');
  }

  function openExternalPlayerModal(file) {
    openExternalVlc(file.stream_url);
  }

  // ==============================================================================
  // FILE REMOVAL (With Confirmation Dialog)
  // ==============================================================================

  function askDeleteConfirmation(fileId) {
    pendingDeleteFileId = fileId;
    confirmBackdrop.classList.add('active');
    triggerHaptic('medium');
  }

  btnCancelDelete.addEventListener('click', () => {
    confirmBackdrop.classList.remove('active');
    pendingDeleteFileId = null;
  });

  btnConfirmDelete.addEventListener('click', async () => {
    if (!pendingDeleteFileId) return;
    const fileId = pendingDeleteFileId;
    confirmBackdrop.classList.remove('active');

    const userId = currentUser?.id || '986380678';
    try {
      const res = await fetch(`/api/file/${fileId}?user_id=${userId}`, {
        method: 'DELETE'
      });
      const data = await res.json();
      if (data.status === 'success') {
        showToast('File removed from library');
        allFiles = allFiles.filter((f) => f.display_id !== fileId && String(f.id) !== fileId);
        renderFileList(allFiles);
        if (currentActiveFile && (currentActiveFile.display_id === fileId || String(currentActiveFile.id) === fileId)) {
          showDashboardView();
        }
      } else {
        showToast('Unable to remove file');
      }
    } catch (e) {
      showToast('Network error while removing');
    }
    pendingDeleteFileId = null;
  });

  // Copy helper
  function copyToClipboard(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(() => {
        showToast('Link copied to clipboard');
      }).catch(() => fallbackCopy(text));
    } else {
      fallbackCopy(text);
    }
  }

  function fallbackCopy(text) {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    showToast('Link copied to clipboard');
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // ==============================================================================
  // INITIALIZATION
  // ==============================================================================

  initUser();
  setupTelegramBackButton();
  loadUserFiles();

  // If initial file data was injected into window.__INITIAL_FILE__, auto-open player
  if (window.__INITIAL_FILE__) {
    showPlayerView(window.__INITIAL_FILE__);
  }

})();
