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

  // DOM Elements - Search
  const searchInput = document.getElementById('searchInput');
  const searchClearBtn = document.getElementById('searchClearBtn');
  const fileLibraryGrid = document.getElementById('fileLibraryGrid');
  const filesCountBadge = document.getElementById('filesCountBadge');
  const emptyStateCard = document.getElementById('emptyStateCard');

  // DOM Elements - Player View
  const btnBackLibrary = document.getElementById('btnBackLibrary');
  const playerVideoTitle = document.getElementById('playerVideoTitle');
  const mainVideo = document.getElementById('mainVideo');
  const playerCanvas = document.getElementById('playerCanvas');
  const playerCenterPlay = document.getElementById('playerCenterPlay');
  const playerLoadingSpinner = document.getElementById('playerLoadingSpinner');
  const playerErrorOverlay = document.getElementById('playerErrorOverlay');
  const playerControlsOverlay = document.getElementById('playerControlsOverlay');
  const timelineContainer = document.getElementById('timelineContainer');
  const timelineBuffer = document.getElementById('timelineBuffer');
  const timelineFill = document.getElementById('timelineFill');

  // Player Buttons
  const btnPlay = document.getElementById('btnPlay');
  const iconPlay = document.getElementById('iconPlay');
  const iconPause = document.getElementById('iconPause');
  const btnRewind = document.getElementById('btnRewind');
  const btnForward = document.getElementById('btnForward');
  const btnMute = document.getElementById('btnMute');
  const iconVol = document.getElementById('iconVol');
  const iconMute = document.getElementById('iconMute');
  const timeDisplayLabel = document.getElementById('timeDisplayLabel');
  const btnSpeed = document.getElementById('btnSpeed');
  const speedLabel = document.getElementById('speedLabel');
  const btnTracks = document.getElementById('btnTracks');
  const tracksBadgeDot = document.getElementById('tracksBadgeDot');
  const btnPip = document.getElementById('btnPip');
  const btnFullscreen = document.getElementById('btnFullscreen');

  // Player Bottom Action Buttons
  const btnDownloadMain = document.getElementById('btnDownloadMain');
  const btnCopyLinkMain = document.getElementById('btnCopyLinkMain');
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
    if (!currentActiveFile || !mainVideo) return;
    const cur = mainVideo.currentTime;
    const dur = mainVideo.duration;
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
    if (hasResumedCurrentVideo) return;
    const key = getFileProgressKey(file);
    if (!key) return;
    try {
      const saved = parseFloat(localStorage.getItem(key));
      if (saved && saved > 3 && isFinite(mainVideo.duration) && saved < mainVideo.duration - 8) {
        hasResumedCurrentVideo = true;
        mainVideo.currentTime = saved;
        showToast(`Resumed from ${formatTime(saved)}`);
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
      showDashboardView();
      triggerHaptic('select');
    });
  }

  function showDashboardView() {
    viewDashboard.classList.add('active');
    viewPlayer.classList.remove('active');
    closeTrackSheet();
    if (mainVideo) {
      mainVideo.pause();
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
    btnDownloadMain.href = file.dl_url;
    btnDownloadMain.setAttribute('download', file.name);
    btnDownloadMain.onclick = (e) => {
      e.preventDefault();
      triggerBrowserDownload(file.dl_url);
    };

    btnCopyLinkMain.onclick = () => {
      copyToClipboard(file.stream_url);
    };

    btnExternalPlayer.onclick = () => {
      openExternalPlayerModal(file);
    };

    // Load and play video
    loadVideoSource(file);

    // Probe tracks
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
    const userId = currentUser?.id || '986380678'; // fallback to owner/demo
    try {
      const res = await fetch(`/api/user/files?user_id=${userId}`);
      const data = await res.json();
      if (data.status === 'success' && data.files) {
        allFiles = data.files;
        renderFileList(allFiles);
      } else {
        renderFileList([]);
      }
    } catch (err) {
      console.warn('[Files] Load error:', err);
      renderFileList([]);
    }
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
        copyToClipboard(file.stream_url);
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
  // VIDEO PLAYER ENGINE (Instant Progressive Stream, <400ms Start)
  // ==============================================================================

  function loadVideoSource(file) {
    hasResumedCurrentVideo = false;
    playerErrorOverlay.classList.remove('visible');
    playerLoadingSpinner.classList.add('visible');
    playerCenterPlay.classList.remove('hidden');

    // Remove any previous subtitle tracks
    mainVideo.querySelectorAll('track').forEach((t) => t.remove());

    // Clean progressive streaming URL
    mainVideo.src = file.stream_url;
    mainVideo.load();

    mainVideo.play().then(() => {
      playerCenterPlay.classList.add('hidden');
      resetControlsAutohide();
    }).catch(() => {
      // Browser autoplay restriction before user gesture
      playerLoadingSpinner.classList.remove('visible');
      playerCenterPlay.classList.remove('hidden');
    });
  }

  function startPlayback() {
    if (mainVideo.paused || mainVideo.ended) {
      mainVideo.play().then(() => {
        playerCenterPlay.classList.add('hidden');
        resetControlsAutohide();
      }).catch((err) => {
        console.warn('[Player] Play error:', err);
      });
    }
    triggerHaptic('light');
  }

  function togglePlayState() {
    if (mainVideo.paused || mainVideo.ended) {
      startPlayback();
    } else {
      mainVideo.pause();
      playerCenterPlay.classList.remove('hidden');
      playerControlsOverlay.classList.remove('autohide');
    }
    triggerHaptic('light');
  }

  // Center Red Play Button
  playerCenterPlay.addEventListener('click', (e) => {
    e.stopPropagation();
    startPlayback();
  });

  playerCenterPlay.addEventListener('touchend', (e) => {
    e.stopPropagation();
    e.preventDefault();
    startPlayback();
  });

  btnPlay.addEventListener('click', (e) => {
    e.stopPropagation();
    togglePlayState();
  });

  // Tapping anywhere inside the player canvas:
  // Shows/toggles player controls & settings without interfering with buttons!
  function handlePlayerSurfaceClick(e) {
    if (e.target.closest('.ctrl-btn') || 
        e.target.closest('.btn-tracks-switcher') || 
        e.target.closest('.timeline-track-container') ||
        e.target.closest('#playerCenterPlay') ||
        e.target.closest('#playerErrorOverlay')) {
      return;
    }

    if (playerControlsOverlay.classList.contains('autohide')) {
      resetControlsAutohide();
    } else {
      if (!mainVideo.paused) {
        playerControlsOverlay.classList.add('autohide');
        clearTimeout(hideControlsTimer);
      } else {
        resetControlsAutohide();
      }
    }
    triggerHaptic('light');
  }

  playerCanvas.addEventListener('click', handlePlayerSurfaceClick);

  mainVideo.addEventListener('play', () => {
    playerCenterPlay.classList.add('hidden');
    iconPlay.style.display = 'none';
    iconPause.style.display = 'block';
    resetControlsAutohide();
  });

  mainVideo.addEventListener('pause', () => {
    playerCenterPlay.classList.remove('hidden');
    iconPlay.style.display = 'block';
    iconPause.style.display = 'none';
    playerControlsOverlay.classList.remove('autohide');
  });

  mainVideo.addEventListener('waiting', () => {
    playerLoadingSpinner.classList.add('visible');
  });

  mainVideo.addEventListener('playing', () => {
    playerLoadingSpinner.classList.remove('visible');
  });

  mainVideo.addEventListener('loadedmetadata', () => {
    if (currentActiveFile) {
      checkAndResumeProgress(currentActiveFile);
    }
  });

  mainVideo.addEventListener('canplay', () => {
    if (currentActiveFile && !hasResumedCurrentVideo) {
      checkAndResumeProgress(currentActiveFile);
    }
  });

  let lastProgressSaveTime = 0;
  mainVideo.addEventListener('timeupdate', () => {
    const cur = mainVideo.currentTime;
    const dur = mainVideo.duration;
    timeDisplayLabel.textContent = `${formatTime(cur)} / ${formatTime(dur)}`;

    if (dur && isFinite(dur)) {
      const pct = (cur / dur) * 100;
      timelineFill.style.width = pct + '%';
    }

    // Save playback position periodically
    const now = Date.now();
    if (now - lastProgressSaveTime > 2500) {
      lastProgressSaveTime = now;
      savePlaybackProgress();
    }
  });

  mainVideo.addEventListener('ended', () => {
    if (currentActiveFile) {
      const key = getFileProgressKey(currentActiveFile);
      if (key) {
        try { localStorage.removeItem(key); } catch (_) {}
      }
    }
  });

  mainVideo.addEventListener('progress', () => {
    if (mainVideo.buffered.length > 0 && isFinite(mainVideo.duration)) {
      const end = mainVideo.buffered.end(mainVideo.buffered.length - 1);
      const pct = (end / mainVideo.duration) * 100;
      timelineBuffer.style.width = pct + '%';
    }
  });

  mainVideo.addEventListener('error', () => {
    playerLoadingSpinner.classList.remove('visible');
    playerCenterPlay.classList.add('hidden');
    playerErrorOverlay.classList.add('visible');
  });

  // Skips
  btnRewind.addEventListener('click', (e) => {
    e.stopPropagation();
    mainVideo.currentTime = Math.max(0, mainVideo.currentTime - 10);
    resetControlsAutohide();
    triggerHaptic('light');
  });

  btnForward.addEventListener('click', (e) => {
    e.stopPropagation();
    mainVideo.currentTime = Math.min(mainVideo.duration || Infinity, mainVideo.currentTime + 10);
    resetControlsAutohide();
    triggerHaptic('light');
  });

  // Timeline scrub (Smooth touch & mouse drag)
  function scrubTimeline(e) {
    const rect = timelineContainer.getBoundingClientRect();
    const clientX = e.touches && e.touches.length > 0 ? e.touches[0].clientX : e.clientX;
    const pos = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
    if (isFinite(mainVideo.duration) && mainVideo.duration > 0) {
      mainVideo.currentTime = pos * mainVideo.duration;
      timelineFill.style.width = (pos * 100) + '%';
    }
  }

  let isScrubbing = false;
  timelineContainer.addEventListener('mousedown', (e) => {
    e.stopPropagation();
    isScrubbing = true;
    scrubTimeline(e);
  });

  timelineContainer.addEventListener('touchstart', (e) => {
    e.stopPropagation();
    isScrubbing = true;
    scrubTimeline(e);
  }, { passive: true });

  window.addEventListener('mousemove', (e) => {
    if (isScrubbing) scrubTimeline(e);
  });

  window.addEventListener('touchmove', (e) => {
    if (isScrubbing) scrubTimeline(e);
  }, { passive: true });

  window.addEventListener('mouseup', () => {
    if (isScrubbing) {
      isScrubbing = false;
      savePlaybackProgress();
    }
  });

  window.addEventListener('touchend', () => {
    if (isScrubbing) {
      isScrubbing = false;
      savePlaybackProgress();
    }
  });

  // Volume / Mute
  btnMute.addEventListener('click', (e) => {
    e.stopPropagation();
    mainVideo.muted = !mainVideo.muted;
    iconVol.style.display = mainVideo.muted ? 'none' : 'block';
    iconMute.style.display = mainVideo.muted ? 'block' : 'none';
    resetControlsAutohide();
    triggerHaptic('light');
  });

  // Speed
  btnSpeed.addEventListener('click', (e) => {
    e.stopPropagation();
    currentSpeedIndex = (currentSpeedIndex + 1) % SPEED_OPTIONS.length;
    const spd = SPEED_OPTIONS[currentSpeedIndex];
    mainVideo.playbackRate = spd;
    speedLabel.textContent = `${spd}x`;
    showToast(`Speed: ${spd}x`);
    resetControlsAutohide();
  });

  // PiP & Fullscreen
  btnPip.addEventListener('click', async (e) => {
    e.stopPropagation();
    try {
      if (document.pictureInPictureElement) {
        await document.exitPictureInPicture();
      } else if (mainVideo.requestPictureInPicture) {
        await mainVideo.requestPictureInPicture();
      }
    } catch (_) {}
  });

  btnFullscreen.addEventListener('click', (e) => {
    e.stopPropagation();
    if (document.fullscreenElement) {
      document.exitFullscreen().catch(() => {});
    } else if (playerCanvas.requestFullscreen) {
      playerCanvas.requestFullscreen().catch(() => {});
    }
  });

  // Controls Autohide on Tap
  function resetControlsAutohide() {
    playerControlsOverlay.classList.remove('autohide');
    clearTimeout(hideControlsTimer);
    if (!mainVideo.paused) {
      hideControlsTimer = setTimeout(() => {
        if (!trackSheetContainer.classList.contains('active')) {
          playerControlsOverlay.classList.add('autohide');
        }
      }, 3500);
    }
  }

  playerCanvas.addEventListener('mousemove', resetControlsAutohide);
  playerCanvas.addEventListener('touchstart', resetControlsAutohide);

  // Keyboard shortcuts (Desktop)
  document.addEventListener('keydown', (e) => {
    if (viewPlayer.classList.contains('active') && !trackSheetContainer.classList.contains('active')) {
      if (e.code === 'Space') {
        e.preventDefault();
        togglePlayState();
      } else if (e.code === 'ArrowLeft') {
        mainVideo.currentTime = Math.max(0, mainVideo.currentTime - 10);
      } else if (e.code === 'ArrowRight') {
        mainVideo.currentTime = Math.min(mainVideo.duration || Infinity, mainVideo.currentTime + 10);
      }
    }
  });

  // ==============================================================================
  // AUDIO & SUBTITLE SWITCHER BOTTOM SHEET / MODAL
  // ==============================================================================

  async function probeMediaTracks(identifier) {
    try {
      const res = await fetch(`/api/media/${identifier}/tracks`);
      currentTracksData = await res.json();
      renderTrackLists(currentTracksData);
    } catch (e) {
      console.warn('[Tracks] Probe note:', e);
      currentTracksData = { audio: [], subtitles: [] };
      renderTrackLists(currentTracksData);
    }
  }

  function renderTrackLists(data) {
    const audioTracks = data.audio || [];
    const subTracks = data.subtitles || [];

    // Audio list
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
        const item = document.createElement('div');
        item.className = `track-item-row ${i === activeAudioIndex ? 'selected' : ''}`;
        const name = tr.language_name || tr.title || `Track ${i + 1}`;
        const desc = `${tr.codec?.toUpperCase() || 'AAC'} • ${tr.channels === 6 ? '5.1 Surround' : 'Stereo'}`;

        item.innerHTML = `
          <div class="track-item-left">
            <span class="track-item-name">${escapeHtml(name)}</span>
            <span class="track-item-desc">${escapeHtml(desc)}</span>
          </div>
          <span class="track-check-indicator">✓</span>
        </div>
        `;

        item.addEventListener('click', () => {
          activeAudioIndex = i;
          audioTracksList.querySelectorAll('.track-item-row').forEach((r, idx) => {
            r.classList.toggle('selected', idx === i);
          });
          showToast(`Audio: ${name}`);
          triggerHaptic('select');
        });

        audioTracksList.appendChild(item);
      });
    }

    // Subtitles list
    subTracksList.innerHTML = '';

    // "Off" option
    const offItem = document.createElement('div');
    offItem.className = `track-item-row ${activeSubIndex === -1 ? 'selected' : ''}`;
    offItem.innerHTML = `
      <div class="track-item-left">
        <span class="track-item-name">Off</span>
        <span class="track-item-desc">Subtitles Disabled</span>
      </div>
      <span class="track-check-indicator">✓</span>
    `;
    offItem.addEventListener('click', () => {
      selectSubtitleTrack(-1, null);
    });
    subTracksList.appendChild(offItem);

    subTracks.forEach((sub, i) => {
      const item = document.createElement('div');
      item.className = `track-item-row ${sub.index === activeSubIndex ? 'selected' : ''}`;
      item.dataset.subIndex = sub.index;
      const name = sub.language_name || sub.title || `Subtitle ${i + 1}`;
      const desc = `${sub.codec?.toUpperCase() || 'WebVTT'} • ${sub.forced ? 'Forced' : 'Full'}`;

      item.innerHTML = `
        <div class="track-item-left">
          <span class="track-item-name">${escapeHtml(name)}</span>
          <span class="track-item-desc">${escapeHtml(desc)}</span>
        </div>
        <span class="track-check-indicator">✓</span>
      `;

      item.addEventListener('click', () => {
        selectSubtitleTrack(sub.index, sub);
      });

      subTracksList.appendChild(item);
    });
  }

  function selectSubtitleTrack(index, subObj) {
    activeSubIndex = index;

    // 1. Correctly update selected class on all rows (Off item included!)
    const allRows = subTracksList.querySelectorAll('.track-item-row');
    allRows.forEach((row, i) => {
      if (i === 0) {
        // Off button: selected ONLY when index === -1
        row.classList.toggle('selected', index === -1);
      } else {
        const rowIdx = parseInt(row.dataset.subIndex, 10);
        row.classList.toggle('selected', rowIdx === index);
      }
    });

    // 2. Remove existing track elements
    mainVideo.querySelectorAll('track').forEach((t) => t.remove());

    if (mainVideo.textTracks && mainVideo.textTracks.length > 0) {
      for (let j = 0; j < mainVideo.textTracks.length; j++) {
        mainVideo.textTracks[j].mode = 'disabled';
      }
    }

    if (index === -1 || !subObj) {
      showToast('Subtitles: Off');
      triggerHaptic('select');
      return;
    }

    // 3. Attach WebVTT track
    const trackEl = document.createElement('track');
    trackEl.kind = 'subtitles';
    trackEl.label = subObj.language_name || subObj.title || 'Subtitles';
    trackEl.srclang = subObj.language || 'en';
    trackEl.src = `/api/media/${currentActiveFile.display_id || currentActiveFile.id}/subs/${index}.vtt`;
    trackEl.default = true;

    function activateTrackShowing() {
      try {
        if (trackEl.track) {
          trackEl.track.mode = 'showing';
        }
        if (mainVideo.textTracks && mainVideo.textTracks.length > 0) {
          for (let j = 0; j < mainVideo.textTracks.length; j++) {
            const tt = mainVideo.textTracks[j];
            if (tt.label === trackEl.label || tt.language === trackEl.srclang) {
              tt.mode = 'showing';
            } else {
              tt.mode = 'disabled';
            }
          }
        }
      } catch (e) {
        console.warn('[Subtitles] Mode note:', e);
      }
    }

    trackEl.addEventListener('load', activateTrackShowing);
    mainVideo.appendChild(trackEl);
    activateTrackShowing();

    showToast(`Subtitles: ${subObj.language_name || subObj.title || 'Enabled'}`);
    triggerHaptic('select');
  }

  // Open / Close Track Sheet
  function openTrackSheet() {
    trackModalBackdrop.classList.add('active');
    trackSheetContainer.classList.add('active');
    playerControlsOverlay.classList.remove('autohide');
    triggerHaptic('light');
  }

  function closeTrackSheet() {
    trackModalBackdrop.classList.remove('active');
    trackSheetContainer.classList.remove('active');
    resetControlsAutohide();
  }

  btnTracks.addEventListener('click', (e) => {
    e.stopPropagation();
    openTrackSheet();
  });
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

  // Subtitle size controls
  document.querySelectorAll('.sub-size-pill').forEach((pill) => {
    pill.addEventListener('click', () => {
      document.querySelectorAll('.sub-size-pill').forEach((p) => p.classList.remove('active'));
      pill.classList.add('active');
      const size = pill.dataset.size;
      activeSubSize = size;
      localStorage.setItem('kayi_sub_size', size);

      let px = '18px';
      if (size === 'small') px = '14px';
      if (size === 'large') px = '22px';

      document.documentElement.style.setProperty('--sub-font-size', px);
      subPreviewText.style.fontSize = px;
      triggerHaptic('light');
    });
  });

  // Apply saved subtitle size on startup
  if (activeSubSize) {
    const targetPill = document.querySelector(`.sub-size-pill[data-size="${activeSubSize}"]`);
    if (targetPill) targetPill.click();
  }

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
