/**
 * Kayi Stream Bot - Telegram Mini App Dashboard Controller
 * Built with Obsidian Cinema Dark Theme & Telegram WebApp SDK
 */

(function () {
  'use strict';

  // Telegram WebApp SDK initialization
  const tg = window.Telegram?.WebApp;
  if (tg) {
    try {
      tg.ready();
      tg.expand();
      if (tg.setHeaderColor) tg.setHeaderColor('#0B0C10');
      if (tg.setBackgroundColor) tg.setBackgroundColor('#0B0C10');
    } catch (e) {
      console.warn('[WebApp] Setup error:', e);
    }
  }

  // DOM Elements
  const uAvatar = document.getElementById('uAvatar');
  const uName = document.getElementById('uName');
  const uStatus = document.getElementById('uStatus');
  const activeFilesCount = document.getElementById('activeFilesCount');
  const streamInput = document.getElementById('streamInput');
  const btnStreamNow = document.getElementById('btnStreamNow');
  const filesList = document.getElementById('filesList');
  const toastNotice = document.getElementById('toastNotice');

  // Player Elements
  const mainVideo = document.getElementById('mainVideo');
  const npName = document.getElementById('npName');
  const bigPlayBtn = document.getElementById('bigPlayBtn');
  const btnPlay = document.getElementById('btnPlay');
  const iconPlay = document.getElementById('iconPlay');
  const iconPause = document.getElementById('iconPause');
  const btnRewind = document.getElementById('btnRewind');
  const btnForward = document.getElementById('btnForward');
  const btnMute = document.getElementById('btnMute');
  const iconVolHigh = document.getElementById('iconVolHigh');
  const iconVolMute = document.getElementById('iconVolMute');
  const timeCurrent = document.getElementById('timeCurrent');
  const timeDuration = document.getElementById('timeDuration');
  const seekContainer = document.getElementById('seekContainer');
  const seekFill = document.getElementById('seekFill');
  const seekBuffer = document.getElementById('seekBuffer');
  const btnPip = document.getElementById('btnPip');
  const btnFullscreen = document.getElementById('btnFullscreen');
  const videoStage = document.getElementById('videoStage');
  const spinnerOverlay = document.getElementById('spinnerOverlay');
  const errorOverlay = document.getElementById('errorOverlay');
  const playerActionRow = document.getElementById('playerActionRow');
  const dlActiveBtn = document.getElementById('dlActiveBtn');
  const copyActiveBtn = document.getElementById('copyActiveBtn');

  // Metrics Elements
  const metFiles = document.getElementById('metFiles');
  const metActive = document.getElementById('metActive');
  const metStorage = document.getElementById('metStorage');
  const metDownloads = document.getElementById('metDownloads');

  // State
  let currentUser = tg?.initDataUnsafe?.user || null;
  let activeTab = 'files';
  let currentFile = null;
  let isSeeking = false;

  // Haptic feedback helper
  function haptic(type = 'light') {
    if (!tg?.HapticFeedback) return;
    try {
      if (type === 'light') tg.HapticFeedback.impactOccurred('light');
      else if (type === 'medium') tg.HapticFeedback.impactOccurred('medium');
      else if (type === 'success') tg.HapticFeedback.notificationOccurred('success');
      else if (type === 'select') tg.HapticFeedback.selectionChanged();
    } catch (_) {}
  }

  // Toast Notification
  function showToast(message, isSuccess = true) {
    if (!toastNotice) return;
    const msgEl = toastNotice.querySelector('.toast-msg');
    const iconEl = toastNotice.querySelector('.toast-icon');
    if (msgEl) msgEl.textContent = message;
    if (iconEl) iconEl.textContent = isSuccess ? '✓' : 'ℹ';
    toastNotice.classList.add('visible');
    haptic(isSuccess ? 'success' : 'light');
    setTimeout(() => {
      toastNotice.classList.remove('visible');
    }, 2400);
  }

  // Format Helpers
  function formatTime(seconds) {
    if (isNaN(seconds) || !isFinite(seconds)) return '0:00';
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

  function getCategoryIcon(cat) {
    switch (cat) {
      case 'video': return '🎬';
      case 'audio': return '🎵';
      case 'image': return '🖼️';
      case 'pdf': return '📑';
      default: return '📄';
    }
  }

  // Tab Navigation
  function switchTab(targetTab) {
    activeTab = targetTab;
    haptic('select');
    document.querySelectorAll('.dash-tab-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tab === targetTab);
    });
    document.querySelectorAll('.tab-content-panel').forEach(panel => {
      panel.classList.toggle('active', panel.id === `tab-${targetTab}`);
    });

    if (targetTab === 'metrics') {
      loadStats();
    }
  }

  document.querySelectorAll('.dash-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });

  // User Setup
  function initUserProfile() {
    if (currentUser) {
      const name = currentUser.first_name || 'Streamer';
      uName.textContent = `Hello, ${name}! 👋`;
      uAvatar.textContent = name.charAt(0).toUpperCase();
      const uname = currentUser.username ? `@${currentUser.username}` : `ID: ${currentUser.id}`;
      uStatus.textContent = `${uname} · Connected to Telegram Cloud`;
    } else {
      uName.textContent = 'Welcome to Kayi Stream Hub!';
      uStatus.textContent = 'Telegram Cloud Streaming Engine · 0-Disk Direct RAM';
    }
  }

  // Load User Files
  async function loadUserFiles() {
    if (!currentUser || !currentUser.id) {
      // Non-Telegram browser visitor or preview mode
      renderEmptyState('Send files to @KayiStreamBot in Telegram to stream them instantly here!');
      return;
    }

    try {
      const res = await fetch(`/api/user/files?user_id=${currentUser.id}`);
      const data = await res.json();

      if (data.status === 'success' && data.files && data.files.length > 0) {
        activeFilesCount.textContent = data.files.length;
        renderFileList(data.files);
      } else {
        activeFilesCount.textContent = '0';
        renderEmptyState('You haven\'t uploaded any files yet. Send any media or file to the bot to create streaming links!');
      }
    } catch (err) {
      console.error('[Dashboard] Error loading files:', err);
      renderEmptyState('Unable to load files right now. Please tap Refresh or try again.');
    }
  }

  function renderFileList(files) {
    filesList.innerHTML = '';
    files.forEach(file => {
      const item = document.createElement('div');
      item.className = 'file-stream-item';

      const icon = getCategoryIcon(file.category);
      const isVideo = file.category === 'video' || file.category === 'audio';

      item.innerHTML = `
        <div class="file-item-left">
          <div class="file-type-icon">${icon}</div>
          <div class="file-item-details">
            <div class="file-item-title" title="${escapeHtml(file.name)}">${escapeHtml(file.name)}</div>
            <div class="file-item-meta">
              <span>Ref: ${file.display_id}</span>
              <span>•</span>
              <span>${file.size_fmt}</span>
              <span>•</span>
              <span>${file.quality}</span>
            </div>
          </div>
        </div>
        <div class="file-item-actions">
          ${isVideo ? `<button class="btn-item-action play" data-id="${file.display_id}">▶ Watch</button>` : ''}
          <a class="btn-item-action download" href="${file.dl_url}" download="${escapeHtml(file.name)}">⚡ Download</a>
          <button class="btn-item-action copy" data-url="${file.stream_url}">📋</button>
        </div>
      `;

      // Event handlers
      const playBtn = item.querySelector('.btn-item-action.play');
      if (playBtn) {
        playBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          loadFileToPlayer(file);
        });
      }

      const copyBtn = item.querySelector('.btn-item-action.copy');
      if (copyBtn) {
        copyBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          copyToClipboard(copyBtn.dataset.url);
        });
      }

      item.addEventListener('click', () => {
        if (isVideo) {
          loadFileToPlayer(file);
        } else {
          window.location.href = file.watch_url;
        }
      });

      filesList.appendChild(item);
    });
  }

  function renderEmptyState(message) {
    filesList.innerHTML = `
      <div class="empty-state-card">
        <div class="empty-icon">📁</div>
        <h3 class="empty-title">No Media Active</h3>
        <p class="empty-desc">${escapeHtml(message)}</p>
      </div>
    `;
  }

  // Load File into Embedded Player
  async function loadFileToPlayer(file) {
    currentFile = file;
    switchTab('player');
    haptic('medium');

    npName.textContent = `${file.name} (${file.size_fmt})`;
    playerActionRow.style.display = 'flex';
    dlActiveBtn.href = file.dl_url;
    dlActiveBtn.setAttribute('download', file.name);

    copyActiveBtn.onclick = () => {
      copyToClipboard(file.stream_url);
    };

    // Load stream into video element
    spinnerOverlay.classList.add('visible');
    errorOverlay.classList.remove('visible');

    mainVideo.src = file.stream_url;
    mainVideo.load();
    mainVideo.play().catch(() => {
      // Autoplay might be restricted before user interaction
      spinnerOverlay.classList.remove('visible');
      bigPlayBtn.classList.remove('hidden');
    });
  }

  // Quick Stream Search
  async function performQuickStream() {
    const query = streamInput.value.trim();
    if (!query) {
      showToast('Please enter a File Ref ID or link', false);
      return;
    }

    // Extract ID if URL was pasted
    let cleanId = query;
    if (query.includes('/watch/')) {
      cleanId = query.split('/watch/')[1].split(/[?#]/)[0];
    } else if (query.includes('/stream/')) {
      cleanId = query.split('/stream/')[1].split(/[?#]/)[0];
    } else if (query.includes('/dl/')) {
      cleanId = query.split('/dl/')[1].split(/[?#]/)[0];
    }

    try {
      showToast('Locating stream...', false);
      const res = await fetch(`/api/file/${encodeURIComponent(cleanId)}`);
      const data = await res.json();

      if (data.status === 'success' && data.file) {
        showToast('Stream found! Loading player...');
        loadFileToPlayer(data.file);
      } else {
        showToast('File not found or expired', false);
      }
    } catch (err) {
      showToast('Error connecting to server', false);
    }
  }

  btnStreamNow.addEventListener('click', performQuickStream);
  streamInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') performQuickStream();
  });

  // Video Player Controls Logic
  function togglePlay() {
    if (mainVideo.paused || mainVideo.ended) {
      mainVideo.play().catch(e => console.log('Play blocked:', e));
    } else {
      mainVideo.pause();
    }
    haptic('light');
  }

  bigPlayBtn.addEventListener('click', togglePlay);
  btnPlay.addEventListener('click', togglePlay);

  mainVideo.addEventListener('play', () => {
    bigPlayBtn.classList.add('hidden');
    iconPlay.style.display = 'none';
    iconPause.style.display = 'inline-block';
  });

  mainVideo.addEventListener('pause', () => {
    bigPlayBtn.classList.remove('hidden');
    iconPlay.style.display = 'inline-block';
    iconPause.style.display = 'none';
  });

  mainVideo.addEventListener('waiting', () => {
    spinnerOverlay.classList.add('visible');
  });

  mainVideo.addEventListener('playing', () => {
    spinnerOverlay.classList.remove('visible');
  });

  mainVideo.addEventListener('timeupdate', () => {
    if (isSeeking) return;
    const cur = mainVideo.currentTime;
    const dur = mainVideo.duration;
    timeCurrent.textContent = formatTime(cur);

    if (dur && isFinite(dur)) {
      const pct = (cur / dur) * 100;
      seekFill.style.width = pct + '%';
    }
  });

  mainVideo.addEventListener('loadedmetadata', () => {
    spinnerOverlay.classList.remove('visible');
    timeDuration.textContent = formatTime(mainVideo.duration);
  });

  mainVideo.addEventListener('progress', () => {
    if (mainVideo.buffered.length > 0 && isFinite(mainVideo.duration)) {
      const end = mainVideo.buffered.end(mainVideo.buffered.length - 1);
      const pct = (end / mainVideo.duration) * 100;
      seekBuffer.style.width = pct + '%';
    }
  });

  mainVideo.addEventListener('error', () => {
    spinnerOverlay.classList.remove('visible');
    errorOverlay.classList.add('visible');
  });

  // Skips
  btnRewind.addEventListener('click', () => {
    mainVideo.currentTime = Math.max(0, mainVideo.currentTime - 10);
    haptic('light');
  });

  btnForward.addEventListener('click', () => {
    mainVideo.currentTime = Math.min(mainVideo.duration || Infinity, mainVideo.currentTime + 10);
    haptic('light');
  });

  // Mute
  btnMute.addEventListener('click', () => {
    mainVideo.muted = !mainVideo.muted;
    iconVolHigh.style.display = mainVideo.muted ? 'none' : 'inline-block';
    iconVolMute.style.display = mainVideo.muted ? 'inline-block' : 'none';
    haptic('light');
  });

  // Seek
  seekContainer.addEventListener('click', (e) => {
    const rect = seekContainer.getBoundingClientRect();
    const pos = (e.clientX - rect.left) / rect.width;
    if (isFinite(mainVideo.duration)) {
      mainVideo.currentTime = pos * mainVideo.duration;
      seekFill.style.width = (pos * 100) + '%';
    }
    haptic('light');
  });

  // PiP & Fullscreen
  btnPip.addEventListener('click', async () => {
    try {
      if (document.pictureInPictureElement) {
        await document.exitPictureInPicture();
      } else if (mainVideo.requestPictureInPicture) {
        await mainVideo.requestPictureInPicture();
      }
    } catch (_) {}
  });

  btnFullscreen.addEventListener('click', () => {
    if (document.fullscreenElement) {
      document.exitFullscreen().catch(() => {});
    } else if (videoStage.requestFullscreen) {
      videoStage.requestFullscreen().catch(() => {});
    }
  });

  // Load Global Stats
  async function loadStats() {
    try {
      const res = await fetch('/api/stats');
      const data = await res.json();
      if (data.status === 'success') {
        metFiles.textContent = data.total_files.toLocaleString();
        metActive.textContent = data.active_files.toLocaleString();
        metStorage.textContent = data.active_bytes_fmt;
        metDownloads.textContent = data.total_downloads.toLocaleString();
      }
    } catch (e) {
      console.warn('[Dashboard] Stats fetch error:', e);
    }
  }

  // Copy helper
  function copyToClipboard(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(() => {
        showToast('Link copied to clipboard! 📋');
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
    showToast('Link copied to clipboard! 📋');
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;')
              .replace(/</g, '&lt;')
              .replace(/>/g, '&gt;')
              .replace(/"/g, '&quot;')
              .replace(/'/g, '&#039;');
  }

  // Initialize
  initUserProfile();
  loadUserFiles();
  loadStats();

})();
