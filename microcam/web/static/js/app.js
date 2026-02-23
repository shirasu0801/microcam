/**
 * MicroCam フロントエンド共通スクリプト
 */

// ステータス更新
async function updateStatus() {
    try {
        const res = await fetch('/api/status');
        const s = await res.json();
        const fpsEl = document.getElementById('fps-display');
        const detEl = document.getElementById('detection-status');
        const recEl = document.getElementById('recording-status');

        if (fpsEl) fpsEl.textContent = `${s.fps} fps`;
        if (detEl) {
            detEl.textContent = `検知: ${s.detection ? 'ON' : 'OFF'}`;
            detEl.style.color = s.detection ? '#2ecc71' : '#a0a0b0';
        }
        if (recEl) {
            recEl.textContent = s.recording ? '● 録画中' : '';
            recEl.style.color = '#e94560';
        }
    } catch {}
}

// 検知トグル
document.getElementById('toggle-detection')?.addEventListener('click', async () => {
    const res = await fetch('/api/status');
    const s = await res.json();
    await fetch('/api/detection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !s.detection }),
    });
    updateStatus();
});

// 定期更新
if (document.getElementById('fps-display')) {
    setInterval(updateStatus, 2000);
    updateStatus();
}
