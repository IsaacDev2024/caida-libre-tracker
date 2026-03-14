// State variables
let videoPath = "";
let frameUrl = "";
let calibrationPoints = [];
let imgOriginalWidth = 0;
let imgOriginalHeight = 0;

// UI Elements
const uploadZone = document.getElementById('upload-zone');
const videoInput = document.getElementById('video-input');
const canvas = document.getElementById('calibration-canvas');
const ctx = canvas.getContext('2d');
let chartInstance = null;
let fitChartInstance = null;

// Navigate between steps
function showStep(stepNum) {
    document.querySelectorAll('.card').forEach(c => {
        c.classList.remove('active');
        c.classList.add('hidden');
    });
    document.querySelectorAll('.step').forEach(s => s.classList.remove('active'));

    const target = document.getElementById(`step-${stepNum}`);
    target.classList.remove('hidden');
    target.classList.add('active');

    for (let i = 1; i <= stepNum; i++) {
        document.getElementById(`indicator-${i}`).classList.add('active');
    }
}

// ------ STEP 1: UPLOAD ------

uploadZone.addEventListener('click', () => videoInput.click());
uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadZone.classList.add('dragover');
});
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadZone.classList.remove('dragover');
    if (e.dataTransfer.files.length > 0) processUpload(e.dataTransfer.files[0]);
});
videoInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) processUpload(e.target.files[0]);
});

async function processUpload(file) {
    if (!file.type.startsWith('video/')) return alert("Por favor selecciona un video válido.");

    uploadZone.classList.add('hidden');
    document.getElementById('upload-loader').classList.remove('hidden');

    const formData = new FormData();
    formData.append("video", file);

    try {
        const response = await fetch('http://localhost:8000/api/upload', { method: 'POST', body: formData });
        const data = await response.json();
        videoPath = data.video_path;
        frameUrl = data.frame_url;
        initCalibration(frameUrl);
    } catch (err) {
        console.error(err);
        alert("Error al subir el video.");
        uploadZone.classList.remove('hidden');
        document.getElementById('upload-loader').classList.add('hidden');
    }
}

// ------ STEP 2: CALIBRATION ------

function initCalibration(url) {
    showStep(2);
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
        imgOriginalWidth = img.width;
        imgOriginalHeight = img.height;
        setTimeout(() => {
            const container = document.querySelector('.canvas-container');
            const maxWidth = container.clientWidth > 0 ? container.clientWidth : Math.min(window.innerWidth - 100, 800);
            const scale = maxWidth / img.width;
            canvas.width = maxWidth;
            canvas.height = img.height * scale;
            ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
            canvas.baseImg = img;
        }, 50);
    };
    img.src = url;
}

canvas.addEventListener('mousedown', (e) => {
    if (calibrationPoints.length >= 2) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    calibrationPoints.push({ x, y });
    redrawCanvas();
    if (calibrationPoints.length === 2) {
        document.getElementById('btn-next-step2').removeAttribute('disabled');
    }
});

function redrawCanvas() {
    ctx.drawImage(canvas.baseImg, 0, 0, canvas.width, canvas.height);
    calibrationPoints.forEach((p, index) => {
        ctx.beginPath();
        ctx.arc(p.x, p.y, 5, 0, 2 * Math.PI);
        ctx.fillStyle = '#ef4444';
        ctx.fill();
        ctx.lineWidth = 2;
        ctx.strokeStyle = '#ffffff';
        ctx.stroke();
        if (index > 0) {
            ctx.beginPath();
            ctx.moveTo(calibrationPoints[index - 1].x, calibrationPoints[index - 1].y);
            ctx.lineTo(p.x, p.y);
            ctx.strokeStyle = '#10b981';
            ctx.lineWidth = 2;
            ctx.stroke();
        }
    });
}

document.getElementById('btn-next-step2').addEventListener('click', () => {
    showStep(3);
    startStream();
});

// ------ STEP 3: HSV TUNING (MJPEG STREAM FROM BACKEND) ------

const streamImg = document.getElementById('filtered-stream');

function buildStreamUrl() {
    const params = new URLSearchParams({
        video_path: videoPath,
        l_h: document.getElementById('l_h').value,
        u_h: document.getElementById('u_h').value,
        l_s: document.getElementById('l_s').value,
        u_s: document.getElementById('u_s').value,
        l_v: document.getElementById('l_v').value,
        u_v: document.getElementById('u_v').value,
    });
    return `http://localhost:8000/api/tune-stream?${params.toString()}`;
}

function startStream() {
    streamImg.src = buildStreamUrl();
}

function restartStream() {
    // Changing src restarts the MJPEG stream with new HSV params
    streamImg.src = '';
    setTimeout(() => {
        streamImg.src = buildStreamUrl();
    }, 50);
}

// Bidirectional slider <-> number input sync + restart stream on change
const sliderIds = ['l_h', 'u_h', 'l_s', 'u_s', 'l_v', 'u_v'];
let streamDebounce = null;

sliderIds.forEach(id => {
    const slider = document.getElementById(id);
    const numInput = document.getElementById(`num-${id}`);

    slider.addEventListener('input', () => {
        numInput.value = slider.value;
        clearTimeout(streamDebounce);
        streamDebounce = setTimeout(restartStream, 300);
    });

    numInput.addEventListener('input', () => {
        let val = parseInt(numInput.value);
        const min = parseInt(numInput.min);
        const max = parseInt(numInput.max);
        if (isNaN(val)) return;
        if (val < min) val = min;
        if (val > max) val = max;
        slider.value = val;
        numInput.value = val;
        clearTimeout(streamDebounce);
        streamDebounce = setTimeout(restartStream, 300);
    });
});

// ------ STEP 4: PROCESSING & CHART ------

document.getElementById('btn-analyze').addEventListener('click', async () => {
    // Stop the stream
    streamImg.src = '';

    document.getElementById('processing-overlay').classList.remove('hidden');

    const realDistVal = document.getElementById('real-distance').value;
    if (!realDistVal || parseFloat(realDistVal) <= 0) {
        document.getElementById('processing-overlay').classList.add('hidden');
        return alert("Por favor ingresa la distancia real en metros en el paso de calibración.");
    }

    const payload = {
        video_path: videoPath,
        l_h: parseInt(document.getElementById('l_h').value),
        u_h: parseInt(document.getElementById('u_h').value),
        l_s: parseInt(document.getElementById('l_s').value),
        u_s: parseInt(document.getElementById('u_s').value),
        l_v: parseInt(document.getElementById('l_v').value),
        u_v: parseInt(document.getElementById('u_v').value),
        pt1_x: Math.round(calibrationPoints[0].x),
        pt1_y: Math.round(calibrationPoints[0].y),
        pt2_x: Math.round(calibrationPoints[1].x),
        pt2_y: Math.round(calibrationPoints[1].y),
        real_distance: parseFloat(realDistVal),
        original_w: canvas.width,
        original_h: canvas.height
    };

    try {
        const response = await fetch('http://localhost:8000/api/process', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await response.json();
        if (result.data && result.data.length > 0) {
            renderResults(result.data);
            showStep(4);
        } else {
            alert("No se detectó el objeto en el video. Ajusta los valores HSV e intenta de nuevo.");
        }
    } catch (err) {
        console.error(err);
        alert("Ocurrió un error al procesar el video.");
    } finally {
        document.getElementById('processing-overlay').classList.add('hidden');
    }
});

let globalData = [];

function renderResults(data) {
    globalData = data;
    const tbody = document.querySelector('#results-table tbody');
    tbody.innerHTML = '';
    const labels = [];
    const positions = [];

    data.forEach(row => {
        labels.push(row.time.toFixed(3));
        positions.push(row.position);
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${row.frame}</td><td>${row.time.toFixed(3)}</td><td>${row.position.toFixed(4)}</td>`;
        tbody.appendChild(tr);
    });

    setTimeout(() => {
        renderChart(labels, positions);
        fetchCurveFit(data);
    }, 150);
}

function renderChart(labels, data) {
    const ctxChart = document.getElementById('results-chart').getContext('2d');
    if (chartInstance) chartInstance.destroy();

    Chart.defaults.color = '#94a3b8';
    Chart.defaults.font.family = "'Plus Jakarta Sans', sans-serif";

    chartInstance = new Chart(ctxChart, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Posición Y (Metros)',
                data: data,
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                borderWidth: 2,
                pointBackgroundColor: '#8b5cf6',
                pointRadius: 4,
                pointHoverRadius: 6,
                fill: true,
                tension: 0.2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: true, position: 'top' },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.9)',
                    titleColor: '#fff',
                    bodyColor: '#e2e8f0',
                    borderColor: 'rgba(148, 163, 184, 0.2)',
                    borderWidth: 1,
                    padding: 10,
                    callbacks: {
                        label: (ctx) => `Posición: ${ctx.parsed.y.toFixed(4)}m`
                    }
                }
            },
            scales: {
                x: { title: { display: true, text: 'Tiempo (s)' }, grid: { color: 'rgba(148, 163, 184, 0.1)' } },
                y: { title: { display: true, text: 'Posición (Metros)' }, grid: { color: 'rgba(148, 163, 184, 0.1)' } }
            }
        }
    });
}

// ------ CURVE FIT ------

async function fetchCurveFit(data) {
    const times = data.map(d => d.time);
    const positions = data.map(d => d.position);

    try {
        const response = await fetch('http://localhost:8000/api/fit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ times, positions })
        });

        if (!response.ok) {
            console.error('Fit request failed');
            return;
        }

        const fit = await response.json();
        renderFitResults(fit, times, positions);
    } catch (err) {
        console.error('Curve fit error:', err);
    }
}

function renderFitResults(fit, originalTimes, originalPositions) {
    const section = document.getElementById('fit-section');
    section.classList.remove('hidden');

    document.getElementById('fit-y0').textContent = fit.y0.toFixed(4) + ' m';
    document.getElementById('fit-v0').textContent = fit.v0.toFixed(4) + ' m/s';
    document.getElementById('fit-g').textContent = fit.g.toFixed(4) + ' m/s²';
    document.getElementById('fit-sigma-y0').textContent = `σ = ${fit.sigma_y0.toFixed(4)}`;
    document.getElementById('fit-sigma-v0').textContent = `σ = ${fit.sigma_v0.toFixed(4)}`;
    document.getElementById('fit-sigma-g').textContent = `σ = ${fit.sigma_g.toFixed(4)}`;

    const formulaBox = document.getElementById('fit-formula');
    const sign_v0 = fit.v0 >= 0 ? '+' : '−';
    const sign_g = fit.g >= 0 ? '−' : '+';
    const abs_v0 = Math.abs(fit.v0).toFixed(4);
    const half_g = Math.abs(fit.g / 2).toFixed(4);
    const y0_str = fit.y0.toFixed(4);

    formulaBox.innerHTML = `
        <div class="formula-title">Fórmula evaluada:</div>
        <div class="formula-text">
            y(t) = ${y0_str} ${sign_v0} ${abs_v0}·t ${sign_g} ${half_g}·t²
        </div>
    `;

    setTimeout(() => renderFitChart(fit, originalTimes, originalPositions), 100);
}

function renderFitChart(fit, originalTimes, originalPositions) {
    const ctxChart = document.getElementById('fit-chart').getContext('2d');
    if (fitChartInstance) fitChartInstance.destroy();

    fitChartInstance = new Chart(ctxChart, {
        type: 'scatter',
        data: {
            datasets: [
                {
                    label: 'Datos experimentales',
                    data: originalTimes.map((t, i) => ({ x: t, y: originalPositions[i] })),
                    backgroundColor: 'rgba(139, 92, 246, 0.8)',
                    borderColor: '#8b5cf6',
                    pointRadius: 5,
                    pointHoverRadius: 7,
                    showLine: false,
                    order: 2
                },
                {
                    label: 'Ajuste: y₀ + v₀t − (g/2)t²',
                    data: fit.fit_t.map((t, i) => ({ x: t, y: fit.fit_y[i] })),
                    borderColor: '#f59e0b',
                    backgroundColor: 'rgba(245, 158, 11, 0.1)',
                    pointRadius: 0,
                    borderWidth: 3,
                    showLine: true,
                    fill: false,
                    tension: 0.4,
                    order: 1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: { usePointStyle: true, pointStyle: 'circle' }
                },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.9)',
                    titleColor: '#fff',
                    bodyColor: '#e2e8f0',
                    borderColor: 'rgba(148, 163, 184, 0.2)',
                    borderWidth: 1,
                    padding: 10
                }
            },
            scales: {
                x: {
                    type: 'linear',
                    title: { display: true, text: 'Tiempo (s)' },
                    grid: { color: 'rgba(148, 163, 184, 0.1)' }
                },
                y: {
                    title: { display: true, text: 'Posición (m)' },
                    grid: { color: 'rgba(148, 163, 184, 0.1)' }
                }
            }
        }
    });
}

// ------ ACTIONS ------

document.getElementById('btn-restart').addEventListener('click', () => window.location.reload());

document.getElementById('btn-export-csv').addEventListener('click', () => {
    if (!globalData.length) return;
    let csvStr = "Frame,Tiempo(s),Posicion_Y(m)\n";
    globalData.forEach(row => { csvStr += `${row.frame},${row.time},${row.position}\n`; });
    const blob = new Blob([csvStr], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'resultados_caida_libre.csv';
    a.click();
    URL.revokeObjectURL(url);
});
