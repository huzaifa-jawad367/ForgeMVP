export function createPrivacySample() {
  const canvas = document.createElement('canvas');
  canvas.width = 480;
  canvas.height = 360;
  const context = canvas.getContext('2d');
  context.fillStyle = '#14363e';
  context.fillRect(0, 0, 480, 360);
  context.fillStyle = '#27768d';
  context.fillRect(125, 240, 230, 120);
  context.fillStyle = '#cc9978';
  context.beginPath();
  context.ellipse(240, 150, 85, 108, 0, 0, Math.PI * 2);
  context.fill();
  context.strokeStyle = '#b77c62';
  context.lineWidth = 2;
  for (let y = 85; y < 225; y += 9) {
    context.beginPath();
    context.moveTo(185, y);
    context.lineTo(295, y);
    context.stroke();
  }
  context.fillStyle = '#203740';
  context.fillRect(198, 128, 20, 8);
  context.fillRect(262, 128, 20, 8);
  context.beginPath();
  context.arc(240, 175, 30, 0.15, Math.PI - 0.15);
  context.strokeStyle = '#493f3d';
  context.lineWidth = 5;
  context.stroke();
  context.fillStyle = '#c8e5e7';
  context.font = '14px sans-serif';
  context.fillText('SYNTHETIC TEST IMAGE', 18, 338);
  const bytes = Uint8Array.from(atob(canvas.toDataURL('image/png').split(',')[1]), character => character.charCodeAt(0));
  return new File([bytes], 'synthetic-skin-sample.png', { type: 'image/png' });
}
