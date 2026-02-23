/**
 * 検知除外エリア描画ツール
 */

function initMaskEditor(canvasId, brushSizeId, clearBtnId, saveBtnId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const brushInput = document.getElementById(brushSizeId);
    let drawing = false;

    // 初期状態: 白（検知対象）で塗りつぶし
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // 既存マスクを読み込み
    const img = new Image();
    img.onload = () => {
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    };
    img.src = '/api/mask?' + Date.now();

    function getPos(e) {
        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;
        const clientX = e.touches ? e.touches[0].clientX : e.clientX;
        const clientY = e.touches ? e.touches[0].clientY : e.clientY;
        return {
            x: (clientX - rect.left) * scaleX,
            y: (clientY - rect.top) * scaleY,
        };
    }

    function draw(e) {
        if (!drawing) return;
        const pos = getPos(e);
        const size = parseInt(brushInput.value);
        ctx.fillStyle = '#000000'; // 黒 = 除外
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, size / 2, 0, Math.PI * 2);
        ctx.fill();
    }

    canvas.addEventListener('mousedown', (e) => { drawing = true; draw(e); });
    canvas.addEventListener('mousemove', draw);
    canvas.addEventListener('mouseup', () => { drawing = false; });
    canvas.addEventListener('mouseleave', () => { drawing = false; });

    // タッチ対応
    canvas.addEventListener('touchstart', (e) => { e.preventDefault(); drawing = true; draw(e); });
    canvas.addEventListener('touchmove', (e) => { e.preventDefault(); draw(e); });
    canvas.addEventListener('touchend', () => { drawing = false; });

    // クリア
    document.getElementById(clearBtnId)?.addEventListener('click', () => {
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
    });

    // 保存
    document.getElementById(saveBtnId)?.addEventListener('click', async () => {
        const dataUrl = canvas.toDataURL('image/png');
        const res = await fetch('/api/mask', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: dataUrl }),
        });
        const r = await res.json();
        alert(r.ok ? 'マスクを保存しました' : 'エラー');
    });
}
