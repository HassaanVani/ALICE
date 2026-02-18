export function createUIDemo(THREE) {
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0a1a);

    scene.add(new THREE.AmbientLight(0x404060, 0.3));
    const mainLight = new THREE.DirectionalLight(0x6366f1, 0.5);
    mainLight.position.set(0, 5, 5);
    scene.add(mainLight);

    const uiGroup = new THREE.Group();
    const interactiveElements = [];

    const createPanel = (width, height, color, opacity = 0.9) => {
        const geo = new THREE.PlaneGeometry(width, height);
        const mat = new THREE.MeshBasicMaterial({
            color,
            transparent: true,
            opacity,
            side: THREE.DoubleSide
        });
        return new THREE.Mesh(geo, mat);
    };

    const createBorder = (width, height, thickness, color) => {
        const group = new THREE.Group();
        const mat = new THREE.MeshBasicMaterial({ color });
        const hGeo = new THREE.PlaneGeometry(width, thickness);
        const vGeo = new THREE.PlaneGeometry(thickness, height);

        const top = new THREE.Mesh(hGeo, mat); top.position.y = height / 2;
        const bottom = new THREE.Mesh(hGeo, mat); bottom.position.y = -height / 2;
        const left = new THREE.Mesh(vGeo, mat); left.position.x = -width / 2;
        const right = new THREE.Mesh(vGeo, mat); right.position.x = width / 2;

        group.add(top, bottom, left, right);
        return group;
    };

    const mainMonitor = new THREE.Group();
    const monitorScreen = createPanel(8, 5, 0x111122, 0.95);
    mainMonitor.add(monitorScreen);

    const monitorFrame = createBorder(8.2, 5.2, 0.08, 0x3b82f6);
    monitorFrame.position.z = 0.01;
    mainMonitor.add(monitorFrame);

    const titleBar = createPanel(7.8, 0.4, 0x1e3a5f, 1);
    titleBar.position.set(0, 2.1, 0.02);
    mainMonitor.add(titleBar);

    const closeBtn = createPanel(0.3, 0.3, 0xff4444, 1);
    closeBtn.position.set(3.6, 2.1, 0.03);
    closeBtn.userData = { type: 'button', action: 'close', baseColor: 0xff4444 };
    interactiveElements.push(closeBtn);
    mainMonitor.add(closeBtn);

    const minBtn = createPanel(0.3, 0.3, 0xffaa00, 1);
    minBtn.position.set(3.2, 2.1, 0.03);
    minBtn.userData = { type: 'button', action: 'minimize', baseColor: 0xffaa00 };
    interactiveElements.push(minBtn);
    mainMonitor.add(minBtn);

    const maxBtn = createPanel(0.3, 0.3, 0x22cc44, 1);
    maxBtn.position.set(2.8, 2.1, 0.03);
    maxBtn.userData = { type: 'button', action: 'maximize', baseColor: 0x22cc44 };
    interactiveElements.push(maxBtn);
    mainMonitor.add(maxBtn);

    const appIcons = [
        { name: 'Files', color: 0x6366f1, x: -3 },
        { name: 'Browser', color: 0x22d3ee, x: -1.5 },
        { name: 'Terminal', color: 0x22c55e, x: 0 },
        { name: 'Settings', color: 0x8b5cf6, x: 1.5 },
        { name: 'Music', color: 0xf43f5e, x: 3 }
    ];

    appIcons.forEach(app => {
        const icon = createPanel(0.8, 0.8, app.color, 1);
        icon.position.set(app.x, 0.5, 0.03);
        icon.userData = { type: 'icon', name: app.name, baseColor: app.color };
        interactiveElements.push(icon);
        mainMonitor.add(icon);
    });

    const volumeTrack = createPanel(4, 0.15, 0x333355, 1);
    volumeTrack.position.set(-1, -1, 0.02);
    mainMonitor.add(volumeTrack);

    const volumeHandle = createPanel(0.25, 0.35, 0x6366f1, 1);
    volumeHandle.position.set(-1, -1, 0.03);
    volumeHandle.userData = { type: 'slider', minX: -3, maxX: 1, value: 0.5 };
    interactiveElements.push(volumeHandle);
    mainMonitor.add(volumeHandle);

    const brightnessTrack = createPanel(4, 0.15, 0x333355, 1);
    brightnessTrack.position.set(-1, -1.6, 0.02);
    mainMonitor.add(brightnessTrack);

    const brightnessHandle = createPanel(0.25, 0.35, 0xfbbf24, 1);
    brightnessHandle.position.set(0, -1.6, 0.03);
    brightnessHandle.userData = { type: 'slider', minX: -3, maxX: 1, value: 0.75 };
    interactiveElements.push(brightnessHandle);
    mainMonitor.add(brightnessHandle);

    const keyboard = new THREE.Group();
    const keyboardBase = createPanel(6, 2, 0x1a1a2e, 0.95);
    keyboard.add(keyboardBase);

    const keyRows = [
        ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0'],
        ['Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P'],
        ['A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L'],
        ['Z', 'X', 'C', 'V', 'B', 'N', 'M']
    ];

    let typedText = '';
    const textDisplay = createPanel(5.5, 0.5, 0x0a0a15, 1);
    textDisplay.position.set(0, 0.6, 0.02);
    keyboard.add(textDisplay);

    keyRows.forEach((row, rowIdx) => {
        const rowOffset = rowIdx * 0.15;
        row.forEach((key, keyIdx) => {
            const keyBtn = createPanel(0.4, 0.35, 0x2a2a4e, 1);
            const startX = -(row.length * 0.45) / 2 + 0.225;
            keyBtn.position.set(startX + keyIdx * 0.45 + rowOffset * 0.2, -0.3 - rowIdx * 0.4, 0.02);
            keyBtn.userData = { type: 'key', char: key, baseColor: 0x2a2a4e };
            interactiveElements.push(keyBtn);
            keyboard.add(keyBtn);
        });
    });

    const spaceBar = createPanel(2.5, 0.35, 0x2a2a4e, 1);
    spaceBar.position.set(0, -1.9, 0.02);
    spaceBar.userData = { type: 'key', char: ' ', baseColor: 0x2a2a4e };
    interactiveElements.push(spaceBar);
    keyboard.add(spaceBar);

    keyboard.position.set(0, -4, 1);
    keyboard.rotation.x = -0.4;

    mainMonitor.position.set(0, 1, -2);
    uiGroup.add(mainMonitor);
    uiGroup.add(keyboard);

    const sidePanel = new THREE.Group();
    const sideBg = createPanel(2.5, 4, 0x111122, 0.9);
    sidePanel.add(sideBg);

    const sideBorder = createBorder(2.6, 4.1, 0.05, 0x22d3ee);
    sideBorder.position.z = 0.01;
    sidePanel.add(sideBorder);

    const notifications = [
        { text: 'New message', color: 0x3b82f6 },
        { text: 'Update ready', color: 0x22c55e },
        { text: 'Low battery', color: 0xfbbf24 }
    ];

    notifications.forEach((notif, i) => {
        const notifBox = createPanel(2.2, 0.6, notif.color, 0.8);
        notifBox.position.set(0, 1.2 - i * 0.8, 0.02);
        notifBox.userData = { type: 'notification', index: i, baseColor: notif.color };
        interactiveElements.push(notifBox);
        sidePanel.add(notifBox);
    });

    sidePanel.position.set(5.5, 0.5, -1);
    sidePanel.rotation.y = -0.3;
    uiGroup.add(sidePanel);

    scene.add(uiGroup);

    const gridFloor = new THREE.GridHelper(20, 40, 0x1a1a3e, 0x0a0a1e);
    gridFloor.position.y = -3;
    scene.add(gridFloor);

    let hoveredElement = null;
    let activeSlider = null;
    const raycaster = new THREE.Raycaster();

    const update = (delta, elapsed, cursorData, camera) => {
        if (!cursorData || !camera || !cursorData.visible) {
            if (hoveredElement) {
                hoveredElement.material.color.setHex(hoveredElement.userData.baseColor);
                hoveredElement.scale.setScalar(1);
                hoveredElement = null;
            }
            return;
        }

        const ndc = new THREE.Vector2(
            (cursorData.x / window.innerWidth) * 2 - 1,
            -(cursorData.y / window.innerHeight) * 2 + 1
        );

        raycaster.setFromCamera(ndc, camera);
        const intersects = raycaster.intersectObjects(interactiveElements);

        if (hoveredElement && (!intersects.length || intersects[0].object !== hoveredElement)) {
            hoveredElement.material.color.setHex(hoveredElement.userData.baseColor);
            hoveredElement.scale.setScalar(1);
            hoveredElement = null;
        }

        if (intersects.length > 0) {
            const hit = intersects[0].object;
            hoveredElement = hit;

            const brighterColor = new THREE.Color(hit.userData.baseColor).multiplyScalar(1.5);
            hit.material.color.copy(brighterColor);
            hit.scale.setScalar(1.1);

            if (cursorData.clicking) {
                if (hit.userData.type === 'slider') {
                    const localPoint = hit.parent.worldToLocal(intersects[0].point.clone());
                    hit.position.x = Math.max(hit.userData.minX, Math.min(hit.userData.maxX, localPoint.x));
                } else if (hit.userData.type === 'key' && !hit.userData.justClicked) {
                    hit.userData.justClicked = true;
                    typedText += hit.userData.char;
                    hit.scale.setScalar(0.9);
                } else if (hit.userData.type === 'icon' && !hit.userData.justClicked) {
                    hit.userData.justClicked = true;
                    hit.scale.setScalar(1.3);
                } else if (hit.userData.type === 'notification' && !hit.userData.justClicked) {
                    hit.userData.justClicked = true;
                    hit.material.opacity = 0.3;
                }
            } else {
                interactiveElements.forEach(el => {
                    el.userData.justClicked = false;
                    if (el.userData.type === 'notification') {
                        el.material.opacity = 0.8;
                    }
                });
            }
        }

        uiGroup.children.forEach(child => {
            child.position.y += Math.sin(elapsed + child.position.x) * 0.0003;
        });
    };

    return {
        scene,
        update,
        defaultDistance: 8,
        minDistance: 4,
        maxDistance: 15,
        isInteractive: true
    };
}

export const metadata = { name: "2D Interface", category: "Interactive", description: "UI interaction demo", interactive: true };
export default (THREE) => createUIDemo(THREE);
