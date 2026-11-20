(function () {
  'use strict';

  const $ = (id) => document.getElementById(id);

  const video = $('mainVideo');
  const stage = $('videoStage');
  const spinner = $('spinnerOverlay');
  const spText = $('spText');
  const errorOverlay = $('errorOverlay');
  const controlsBar = $('controlsBar');
  const btnPlay = $('btnPlay');
  const iconPlay = $('iconPlay');
  const iconPause = $('iconPause');
  const seekContainer = $('seekContainer');
  const seekFill = $('seekFill');
  const seekBuffer = $('seekBuffer');
  const timeCurrent = $('timeCurrent');
  const timeDuration = $('timeDuration');
  const btnMute = $('btnMute');
  const iconVolHigh = $('iconVolHigh');
  const iconVolMute = $('iconVolMute');
  const volSlider = $('volSlider');
  const btnSettings = $('btnSettings');
  const settingsMenu = $('settingsMenu');
  const btnFullscreen = $('btnFullscreen');
  const audioListEl = $('audioTrackList');
  const subListEl = $('subTrackList');
  const copyLinkBtn = $('copyLinkBtn');
  const toastEl = $('toastNotice');

  let hlsInstance = null;
  let mediaTracks = null;
  let activeSubTrackIndex = -1; // -1 = Off
  let hideControlsTimer = null;

  // Format seconds to H:MM:SS or M:SS
  function formatTime(seconds) {
    if (isNaN(seconds) || seconds < 0) return '0:00';
    const s = Math.floor(seconds);
    const m = Math.floor(s / 60);
    const h = Math.floor(m / 60);
    const sec = s % 60;
    const min = m % 60;
    const secStr = sec < 10 ? '0' + sec : sec;
    if (h > 0) {
      const minStr = min < 10 ? '0' + min : min;
      return `${h}:${minStr}:${secStr}`;
    }
    return `${min}:${secStr}`;
  }

  // Toast notification
  function showToast(msg) {
    if (!toastEl) return;
    toastEl.textContent = msg;
    toastEl.classList.add('visible');
    clearTimeout(toastEl._timer);
    toastEl._timer = setTimeout(() => {
      toastEl.classList.remove('visible');
    }, 2200);
  }

  // Hide / show controls
  function resetControlsTimer() {
    controlsBar.classList.remove('hidden');
    clearTimeout(hideControlsTimer);
    if (!video.paused) {
      hideControlsTimer = setTimeout(() => {
        if (!settingsMenu.classList.contains('open')) {
          controlsBar.classList.add('hidden');
        }
      }, 3000);
    }
  }

  // Play / Pause
  function togglePlay() {
    if (video.paused || video.ended) {
      video.play().catch(() => {});
    } else {
      video.pause();
    }
    resetControlsTimer();
  }

  function updatePlayIcons() {
    if (video.paused || video.ended) {
      iconPlay.style.display = 'block';
      iconPause.style.display = 'none';
    } else {
      iconPlay.style.display = 'none';
      iconPause.style.display = 'block';
    }
  }

  // Seeking
  function updateProgress() {
    if (!video.duration) return;
    const pct = (video.currentTime / video.duration) * 100;
    seekFill.style.width = pct + '%';
    timeCurrent.textContent = formatTime(video.currentTime);

    // Buffer progress
    if (video.buffered.length > 0) {
      const bufferedEnd = video.buffered.end(video.buffered.length - 1);
      const bufPct = (bufferedEnd / video.duration) * 100;
      seekBuffer.style.width = bufPct + '%';
    }
  }

  function seekToPosition(e) {
    if (!video.duration) return;
    const rect = seekContainer.getBoundingClientRect();
    const pos = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    video.currentTime = pos * video.duration;
    updateProgress();
    resetControlsTimer();
  }

  // Volume
  function toggleMute() {
    video.muted = !video.muted;
    updateVolUI();
    resetControlsTimer();
  }

  function updateVolUI() {
    if (video.muted || video.volume === 0) {
      iconVolHigh.style.display = 'none';
      iconVolMute.style.display = 'block';
      volSlider.value = 0;
    } else {
      iconVolHigh.style.display = 'block';
      iconVolMute.style.display = 'none';
      volSlider.value = video.volume;
    }
  }

  // Fullscreen
  function toggleFullscreen() {
    if (!document.fullscreenElement) {
      if (stage.requestFullscreen) {
        stage.requestFullscreen();
      } else if (video.webkitEnterFullscreen) {
        video.webkitEnterFullscreen();
      }
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen();
      }
    }
  }

  // Settings Menu Toggle
  function toggleSettingsMenu(e) {
    if (e) e.stopPropagation();
    settingsMenu.classList.toggle('open');
    resetControlsTimer();
  }

  // Build Audio Track Menu
  function populateAudioTracks(audioTracks) {
    audioListEl.innerHTML = '';
    if (!audioTracks || audioTracks.length === 0) {
      audioListEl.innerHTML = '<div style="font-size:12px;color:#8E8E93;padding:4px 10px;">Default Audio</div>';
      return;
    }

    const savedAudioLang = localStorage.getItem('kayi_audio_lang');
    let activeTrackIdx = 0;

    // Check hls.js active audio track if available
    if (hlsInstance && hlsInstance.audioTracks && hlsInstance.audioTracks.length > 0) {
      activeTrackIdx = hlsInstance.audioTrack >= 0 ? hlsInstance.audioTrack : 0;
    } else {
      // Find default or saved
      const foundIdx = audioTracks.findIndex(
        (t) => (t.language && t.language === savedAudioLang) || (t.title && t.title === savedAudioLang)
      );
      if (foundIdx >= 0) {
        activeTrackIdx = foundIdx;
      } else {
        const defIdx = audioTracks.findIndex((t) => t.default);
        if (defIdx >= 0) activeTrackIdx = defIdx;
      }
    }

    audioTracks.forEach((track, idx) => {
      const btn = document.createElement('button');
      btn.className = 'menu-item' + (idx === activeTrackIdx ? ' active' : '');
      btn.type = 'button';

      const label = track.title || track.language_name || `Audio ${idx + 1}`;
      const sub = track.language_name && track.title && track.language_name !== track.title ? ` (${track.language_name})` : '';

      btn.innerHTML = `
        <div>
          <div>${escapeHtml(label)}</div>
          ${sub ? `<div class="menu-item-sub">${escapeHtml(sub)}</div>` : ''}
        </div>
        <svg class="menu-check" viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
      `;

      btn.addEventListener('click', () => {
        selectAudioTrack(idx, track, audioTracks);
      });

      audioListEl.appendChild(btn);
    });
  }

  function selectAudioTrack(idx, track, allTracks) {
    const currentPos = video.currentTime;
    const wasPlaying = !video.paused;

    if (hlsInstance && hlsInstance.audioTracks && hlsInstance.audioTracks.length > 0) {
      hlsInstance.audioTrack = idx;
    }

    // Remember choice
    const langToSave = track.language || track.title || '';
    if (langToSave) {
      localStorage.setItem('kayi_audio_lang', langToSave);
    }

    // Update active class
    const items = audioListEl.querySelectorAll('.menu-item');
    items.forEach((item, i) => {
      item.classList.toggle('active', i === idx);
    });

    // Keep position
    if (video.currentTime !== currentPos) {
      video.currentTime = currentPos;
    }
    if (wasPlaying && video.paused) {
      video.play().catch(() => {});
    }
  }

  // Build Subtitle Track Menu
  function populateSubtitles(subs) {
    subListEl.innerHTML = '';

    // 1. Off option (always first)
    const offBtn = document.createElement('button');
    offBtn.className = 'menu-item' + (activeSubTrackIndex === -1 ? ' active' : '');
    offBtn.type = 'button';
    offBtn.innerHTML = `
      <span>Off</span>
      <svg class="menu-check" viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
    `;
    offBtn.addEventListener('click', () => selectSubtitleTrack(-1, null));
    subListEl.appendChild(offBtn);

    if (!subs || subs.length === 0) return;

    const savedSubLang = localStorage.getItem('kayi_sub_lang');

    subs.forEach((sub, idx) => {
      const btn = document.createElement('button');
      const isSupported = sub.supported !== false;
      const isActive = activeSubTrackIndex === sub.index;

      btn.className = 'menu-item' + (isActive ? ' active' : '') + (!isSupported ? ' disabled' : '');
      btn.type = 'button';

      const label = sub.title || sub.language_name || `Subtitle ${idx + 1}`;
      const subNote = !isSupported ? ' (Not supported in browser)' : sub.language_name && sub.title !== sub.language_name ? ` (${sub.language_name})` : '';

      btn.innerHTML = `
        <div>
          <div>${escapeHtml(label)}</div>
          ${subNote ? `<div class="menu-item-sub">${escapeHtml(subNote)}</div>` : ''}
        </div>
        <svg class="menu-check" viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
      `;

      if (isSupported) {
        btn.addEventListener('click', () => selectSubtitleTrack(sub.index, sub));
      }
      subListEl.appendChild(btn);

      // Check default / saved on startup
      if (activeSubTrackIndex === -1 && isSupported) {
        if (savedSubLang && (sub.language === savedSubLang || sub.title === savedSubLang)) {
          selectSubtitleTrack(sub.index, sub);
        } else if (!savedSubLang && (sub.default || sub.forced)) {
          selectSubtitleTrack(sub.index, sub);
        }
      }
    });
  }

  function selectSubtitleTrack(streamIndex, subObj) {
    activeSubTrackIndex = streamIndex;

    // Remove existing track elements
    const existing = video.querySelectorAll('track');
    existing.forEach((t) => t.remove());

    if (streamIndex === -1 || !subObj) {
      localStorage.setItem('kayi_sub_lang', 'off');
    } else {
      // Add VTT track
      const trackEl = document.createElement('track');
      trackEl.kind = 'subtitles';
      trackEl.label = subObj.title || subObj.language_name || 'Subtitles';
      trackEl.srclang = subObj.language || 'en';
      trackEl.src = `/api/media/${window.F.id}/subs/${streamIndex}.vtt`;
      trackEl.default = true;

      video.appendChild(trackEl);

      trackEl.addEventListener('load', () => {
        if (video.textTracks && video.textTracks.length > 0) {
          for (let i = 0; i < video.textTracks.length; i++) {
            video.textTracks[i].mode = 'showing';
          }
        }
      });

      const langToSave = subObj.language || subObj.title || '';
      if (langToSave) {
        localStorage.setItem('kayi_sub_lang', langToSave);
      }
    }

    // Refresh UI
    const items = subListEl.querySelectorAll('.menu-item');
    items.forEach((item, i) => {
      if (i === 0) {
        item.classList.toggle('active', streamIndex === -1);
      } else if (mediaTracks && mediaTracks.subtitles && mediaTracks.subtitles[i - 1]) {
        item.classList.toggle('active', mediaTracks.subtitles[i - 1].index === streamIndex);
      }
    });
  }

  // Cycle Subtitles with keyboard 'C'
  function cycleSubtitles() {
    if (!mediaTracks || !mediaTracks.subtitles || mediaTracks.subtitles.length === 0) return;
    const supportedSubs = mediaTracks.subtitles.filter((s) => s.supported !== false);
    if (supportedSubs.length === 0) return;

    if (activeSubTrackIndex === -1) {
      selectSubtitleTrack(supportedSubs[0].index, supportedSubs[0]);
      showToast('Subtitles: ' + (supportedSubs[0].title || supportedSubs[0].language_name));
    } else {
      const currentIdx = supportedSubs.findIndex((s) => s.index === activeSubTrackIndex);
      if (currentIdx >= 0 && currentIdx < supportedSubs.length - 1) {
        const nextSub = supportedSubs[currentIdx + 1];
        selectSubtitleTrack(nextSub.index, nextSub);
        showToast('Subtitles: ' + (nextSub.title || nextSub.language_name));
      } else {
        selectSubtitleTrack(-1, null);
        showToast('Subtitles: Off');
      }
    }
  }

  // Initialize Media Playback
  async function initPlayer() {
    const fileId = window.F.id;

    try {
      spText.textContent = 'Inspecting media streams...';
      const resp = await fetch(`/api/media/${fileId}/tracks`);
      mediaTracks = await resp.json();
    } catch (e) {
      console.warn('Track probe failed, falling back to direct mode:', e);
      mediaTracks = { mode: 'direct', audio: [], subtitles: [] };
    }

    // Populate track menus
    populateAudioTracks(mediaTracks.audio || []);
    populateSubtitles(mediaTracks.subtitles || []);

    const mode = mediaTracks.mode || 'direct';

    if (mode === 'hls') {
      spText.textContent = 'Preparing video stream...';
      startHlsPlayback(fileId);
    } else {
      // Direct Mode
      spText.textContent = 'Loading video...';
      video.src = window.F.stream;
    }
  }

  function startHlsPlayback(fileId) {
    const hlsUrl = `/hls/${fileId}/master.m3u8`;

    if (window.Hls && window.Hls.isSupported()) {
      hlsInstance = new window.Hls({
        maxBufferLength: 30,
        enableWorker: true,
        lowLatencyMode: false
      });

      hlsInstance.loadSource(hlsUrl);
      hlsInstance.attachMedia(video);

      hlsInstance.on(window.Hls.Events.MANIFEST_PARSED, (event, data) => {
        spinner.style.display = 'none';
        if (data.audioTracks && data.audioTracks.length > 0) {
          populateAudioTracks(mediaTracks.audio || []);
        }
      });

      hlsInstance.on(window.Hls.Events.AUDIO_TRACKS_UPDATED, () => {
        populateAudioTracks(mediaTracks.audio || []);
      });

      hlsInstance.on(window.Hls.Events.ERROR, (event, data) => {
        if (data.fatal) {
          switch (data.type) {
            case window.Hls.ErrorTypes.NETWORK_ERROR:
              // Segment or master not yet ready, retry shortly
              hlsInstance.startLoad();
              break;
            case window.Hls.ErrorTypes.MEDIA_ERROR:
              hlsInstance.recoverMediaError();
              break;
            default:
              showPlaybackError();
              break;
          }
        }
      });
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      // Native Safari HLS
      video.src = hlsUrl;
      video.addEventListener('loadedmetadata', () => {
        spinner.style.display = 'none';
      });
    } else {
      showPlaybackError();
    }
  }

  function showPlaybackError() {
    spinner.style.display = 'none';
    errorOverlay.style.display = 'flex';
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // Event Listeners
  video.addEventListener('loadedmetadata', () => {
    timeDuration.textContent = formatTime(video.duration);
    spinner.style.display = 'none';
  });

  video.addEventListener('timeupdate', updateProgress);
  video.addEventListener('play', () => {
    updatePlayIcons();
    resetControlsTimer();
  });
  video.addEventListener('pause', () => {
    updatePlayIcons();
    controlsBar.classList.remove('hidden');
  });
  video.addEventListener('ended', updatePlayIcons);
  video.addEventListener('error', () => {
    showPlaybackError();
  });

  btnPlay.addEventListener('click', togglePlay);
  seekContainer.addEventListener('click', seekToPosition);
  btnMute.addEventListener('click', toggleMute);
  volSlider.addEventListener('input', (e) => {
    video.volume = parseFloat(e.target.value);
    video.muted = video.volume === 0;
    updateVolUI();
  });

  btnSettings.addEventListener('click', toggleSettingsMenu);
  btnFullscreen.addEventListener('click', toggleFullscreen);

  // Close settings menu when clicking outside
  document.addEventListener('click', (e) => {
    if (!settingsMenu.contains(e.target) && e.target !== btnSettings && !btnSettings.contains(e.target)) {
      settingsMenu.classList.remove('open');
    }
  });

  // Desktop hover controls show / hide
  stage.addEventListener('mousemove', resetControlsTimer);
  stage.addEventListener('mouseenter', resetControlsTimer);
  stage.addEventListener('mouseleave', () => {
    if (!video.paused && !settingsMenu.classList.contains('open')) {
      controlsBar.classList.add('hidden');
    }
  });

  // Mobile tap on video toggles controls
  video.addEventListener('click', (e) => {
    if (window.innerWidth <= 768) {
      if (controlsBar.classList.contains('hidden')) {
        resetControlsTimer();
      } else {
        controlsBar.classList.add('hidden');
      }
    } else {
      togglePlay();
    }
  });

  // Keyboard navigation
  document.addEventListener('keydown', (e) => {
    // Ignore when typing in inputs
    if (['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) return;

    switch (e.code) {
      case 'Space':
        e.preventDefault();
        togglePlay();
        break;
      case 'ArrowLeft':
        e.preventDefault();
        video.currentTime = Math.max(0, video.currentTime - 5);
        updateProgress();
        resetControlsTimer();
        break;
      case 'ArrowRight':
        e.preventDefault();
        video.currentTime = Math.min(video.duration || 0, video.currentTime + 5);
        updateProgress();
        resetControlsTimer();
        break;
      case 'ArrowUp':
        e.preventDefault();
        video.volume = Math.min(1, video.volume + 0.1);
        video.muted = false;
        updateVolUI();
        resetControlsTimer();
        break;
      case 'ArrowDown':
        e.preventDefault();
        video.volume = Math.max(0, video.volume - 0.1);
        updateVolUI();
        resetControlsTimer();
        break;
      case 'KeyM':
        toggleMute();
        break;
      case 'KeyC':
        cycleSubtitles();
        break;
      case 'KeyF':
        toggleFullscreen();
        break;
    }
  });

  // Copy Stream Link Button
  if (copyLinkBtn) {
    copyLinkBtn.addEventListener('click', () => {
      const absUrl = new URL(window.F.stream, window.location.href).href;
      navigator.clipboard.writeText(absUrl)
        .then(() => showToast('Link copied to clipboard'))
        .catch(() => showToast('Could not copy link'));
    });
  }

  // Run on start
  initPlayer();
})();
