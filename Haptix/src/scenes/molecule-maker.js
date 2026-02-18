export function createMoleculeMaker(THREE) {
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x050510);

    // Lighting
    scene.add(new THREE.AmbientLight(0x404060, 0.5));
    const mainLight = new THREE.DirectionalLight(0xffffff, 0.8);
    mainLight.position.set(5, 10, 5);
    scene.add(mainLight);
    const backLight = new THREE.DirectionalLight(0x6366f1, 0.3);
    backLight.position.set(-5, -5, -5);
    scene.add(backLight);

    // Atom data with colors and sizes (Van der Waals radii relative)
    const atomData = {
        H: { color: 0xffffff, radius: 0.25, name: 'Hydrogen', symbol: 'H' },
        C: { color: 0x333333, radius: 0.4, name: 'Carbon', symbol: 'C' },
        N: { color: 0x3050f8, radius: 0.38, name: 'Nitrogen', symbol: 'N' },
        O: { color: 0xff2010, radius: 0.35, name: 'Oxygen', symbol: 'O' },
        S: { color: 0xffcc00, radius: 0.5, name: 'Sulfur', symbol: 'S' },
        P: { color: 0xff8000, radius: 0.48, name: 'Phosphorus', symbol: 'P' },
        Cl: { color: 0x1ff01f, radius: 0.45, name: 'Chlorine', symbol: 'Cl' },
        F: { color: 0x90e050, radius: 0.3, name: 'Fluorine', symbol: 'F' }
    };

    // State
    let selectedAtom = null;
    let placedAtoms = [];
    let bonds = [];
    let moleculeGroup = new THREE.Group();
    let buildMode = true;

    const interactiveElements = [];
    const raycaster = new THREE.Raycaster();

    // ======== UI PANEL (Atom Palette) ========
    const uiGroup = new THREE.Group();
    uiGroup.position.set(-5, 2, 0);
    uiGroup.rotation.y = 0.3;

    // Panel background
    const panelGeo = new THREE.PlaneGeometry(2.8, 5);
    const panelMat = new THREE.MeshBasicMaterial({
        color: 0x0a0a20,
        transparent: true,
        opacity: 0.9,
        side: THREE.DoubleSide
    });
    const panel = new THREE.Mesh(panelGeo, panelMat);
    uiGroup.add(panel);

    // Panel border
    const borderMat = new THREE.LineBasicMaterial({ color: 0x6366f1 });
    const borderPoints = [
        new THREE.Vector3(-1.4, 2.5, 0.01),
        new THREE.Vector3(1.4, 2.5, 0.01),
        new THREE.Vector3(1.4, -2.5, 0.01),
        new THREE.Vector3(-1.4, -2.5, 0.01),
        new THREE.Vector3(-1.4, 2.5, 0.01)
    ];
    const borderGeo = new THREE.BufferGeometry().setFromPoints(borderPoints);
    uiGroup.add(new THREE.Line(borderGeo, borderMat));

    // Title
    const titleGeo = new THREE.PlaneGeometry(2.4, 0.4);
    const titleMat = new THREE.MeshBasicMaterial({ color: 0x1a1a40 });
    const titleBg = new THREE.Mesh(titleGeo, titleMat);
    titleBg.position.set(0, 2.1, 0.02);
    uiGroup.add(titleBg);

    // Create atom buttons in the palette
    const atomKeys = Object.keys(atomData);
    const cols = 2;
    const buttonSize = 0.9;
    const spacing = 1.1;

    atomKeys.forEach((key, i) => {
        const atom = atomData[key];
        const col = i % cols;
        const row = Math.floor(i / cols);

        // Button background
        const btnGeo = new THREE.PlaneGeometry(buttonSize, buttonSize);
        const btnMat = new THREE.MeshBasicMaterial({
            color: 0x1e1e3e,
            transparent: true,
            opacity: 0.9
        });
        const btn = new THREE.Mesh(btnGeo, btnMat);
        btn.position.set(
            -0.55 + col * spacing,
            1.3 - row * spacing,
            0.03
        );
        btn.userData = {
            type: 'atom-button',
            atomType: key,
            baseColor: 0x1e1e3e,
            selectedColor: 0x3b82f6
        };
        interactiveElements.push(btn);
        uiGroup.add(btn);

        // Atom sphere preview
        const sphereGeo = new THREE.SphereGeometry(atom.radius * 0.6, 24, 24);
        const sphereMat = new THREE.MeshStandardMaterial({
            color: atom.color,
            metalness: 0.3,
            roughness: 0.6,
            emissive: atom.color,
            emissiveIntensity: 0.1
        });
        const sphere = new THREE.Mesh(sphereGeo, sphereMat);
        sphere.position.set(
            -0.55 + col * spacing,
            1.3 - row * spacing,
            0.15
        );
        sphere.userData = { type: 'atom-preview', atomType: key };
        uiGroup.add(sphere);
    });

    // Clear button
    const clearBtnGeo = new THREE.PlaneGeometry(2.4, 0.45);
    const clearBtnMat = new THREE.MeshBasicMaterial({
        color: 0x991b1b,
        transparent: true,
        opacity: 0.9
    });
    const clearBtn = new THREE.Mesh(clearBtnGeo, clearBtnMat);
    clearBtn.position.set(0, -2.1, 0.03);
    clearBtn.userData = { type: 'clear-button', baseColor: 0x991b1b };
    interactiveElements.push(clearBtn);
    uiGroup.add(clearBtn);

    scene.add(uiGroup);

    // ======== MOLECULE BUILD AREA ========
    moleculeGroup.position.set(1, 0, 0);
    scene.add(moleculeGroup);

    // Grid helper for placement
    const gridHelper = new THREE.GridHelper(8, 16, 0x222244, 0x111133);
    gridHelper.position.set(1, -2.5, 0);
    scene.add(gridHelper);

    // Build slots (attachment points)
    const slots = [];
    const slotPositions = [
        // Main center positions
        new THREE.Vector3(0, 0, 0),
        new THREE.Vector3(1.2, 0, 0),
        new THREE.Vector3(-1.2, 0, 0),
        new THREE.Vector3(0, 1.2, 0),
        new THREE.Vector3(0, -1.2, 0),
        new THREE.Vector3(0, 0, 1.2),
        new THREE.Vector3(0, 0, -1.2),
        // Secondary positions
        new THREE.Vector3(2.4, 0, 0),
        new THREE.Vector3(-2.4, 0, 0),
        new THREE.Vector3(1.2, 1.2, 0),
        new THREE.Vector3(-1.2, 1.2, 0),
        new THREE.Vector3(1.2, -1.2, 0),
        new THREE.Vector3(-1.2, -1.2, 0)
    ];

    slotPositions.forEach((pos, i) => {
        // Outer wireframe indicator
        const slotGeo = new THREE.SphereGeometry(0.25, 16, 16);
        const slotMat = new THREE.MeshBasicMaterial({
            color: 0x6366f1,
            transparent: true,
            opacity: 0.3,
            wireframe: true
        });
        const slot = new THREE.Mesh(slotGeo, slotMat);
        slot.position.copy(pos);

        // Inner solid core
        const coreGeo = new THREE.SphereGeometry(0.1, 12, 12);
        const coreMat = new THREE.MeshBasicMaterial({
            color: 0x6366f1,
            transparent: true,
            opacity: 0.6
        });
        const core = new THREE.Mesh(coreGeo, coreMat);
        slot.add(core);

        slot.userData = {
            type: 'slot',
            index: i,
            occupied: false,
            baseColor: 0x6366f1,
            core: core
        };
        slots.push(slot);
        interactiveElements.push(slot);
        moleculeGroup.add(slot);
    });

    // Selection indicator
    const selectionIndicator = new THREE.Mesh(
        new THREE.RingGeometry(0.4, 0.5, 32),
        new THREE.MeshBasicMaterial({
            color: 0x3b82f6,
            transparent: true,
            opacity: 0.8,
            side: THREE.DoubleSide
        })
    );
    selectionIndicator.visible = false;
    scene.add(selectionIndicator);

    // Current selection display
    const currentSelectionGroup = new THREE.Group();
    currentSelectionGroup.position.set(-5, -1.5, 0);
    currentSelectionGroup.rotation.y = 0.3;

    const selLabelBg = new THREE.Mesh(
        new THREE.PlaneGeometry(2.4, 0.5),
        new THREE.MeshBasicMaterial({ color: 0x1a1a40, transparent: true, opacity: 0.9 })
    );
    currentSelectionGroup.add(selLabelBg);
    scene.add(currentSelectionGroup);

    // ======== HELPER FUNCTIONS ========
    function createAtomMesh(atomType, position) {
        const data = atomData[atomType];
        const geo = new THREE.SphereGeometry(data.radius, 32, 32);
        const mat = new THREE.MeshStandardMaterial({
            color: data.color,
            metalness: 0.4,
            roughness: 0.5,
            emissive: data.color,
            emissiveIntensity: 0.15
        });
        const mesh = new THREE.Mesh(geo, mat);
        mesh.position.copy(position);
        mesh.userData = { type: 'placed-atom', atomType };
        return mesh;
    }

    function createBond(pos1, pos2) {
        const direction = new THREE.Vector3().subVectors(pos2, pos1);
        const length = direction.length();
        const midpoint = new THREE.Vector3().addVectors(pos1, pos2).multiplyScalar(0.5);

        const bondGeo = new THREE.CylinderGeometry(0.08, 0.08, length, 8);
        const bondMat = new THREE.MeshStandardMaterial({
            color: 0x888888,
            metalness: 0.3,
            roughness: 0.7
        });
        const bond = new THREE.Mesh(bondGeo, bondMat);
        bond.position.copy(midpoint);

        // Align cylinder to direction
        bond.quaternion.setFromUnitVectors(
            new THREE.Vector3(0, 1, 0),
            direction.normalize()
        );

        return bond;
    }

    function updateBonds() {
        // Remove existing bonds
        bonds.forEach(bond => moleculeGroup.remove(bond));
        bonds = [];

        // Create bonds between adjacent atoms
        for (let i = 0; i < placedAtoms.length; i++) {
            for (let j = i + 1; j < placedAtoms.length; j++) {
                const dist = placedAtoms[i].position.distanceTo(placedAtoms[j].position);
                if (dist < 2.0) { // Bond distance threshold
                    const bond = createBond(placedAtoms[i].position, placedAtoms[j].position);
                    bonds.push(bond);
                    moleculeGroup.add(bond);
                }
            }
        }
    }

    function clearMolecule() {
        placedAtoms.forEach(atom => {
            interactiveElements.splice(interactiveElements.indexOf(atom), 1);
            moleculeGroup.remove(atom);
        });
        bonds.forEach(bond => moleculeGroup.remove(bond));
        placedAtoms = [];
        bonds = [];
        slots.forEach(slot => {
            slot.userData.occupied = false;
            slot.material.color.setHex(0x6366f1);
            slot.material.opacity = 0.3;
            if (slot.userData.core) {
                slot.userData.core.material.color.setHex(0x6366f1);
            }
            slot.visible = true;
        });
        moleculeGroup.rotation.set(0, 0, 0);
    }

    // ======== INTERACTION LOGIC ========
    let hoveredElement = null;

    const update = (delta, elapsed, cursorData, camera) => {
        // Animate selection indicator
        if (selectionIndicator.visible) {
            selectionIndicator.rotation.z += delta * 2;
            selectionIndicator.lookAt(camera.position);
        }

        // Gentle molecule rotation when viewing
        if (!buildMode && placedAtoms.length > 0) {
            moleculeGroup.rotation.y += delta * 0.3;
        }

        // Slot pulsing animation
        slots.forEach((slot, i) => {
            if (!slot.userData.occupied) {
                slot.material.opacity = 0.3 + Math.sin(elapsed * 2 + i * 0.5) * 0.15;
            }
        });

        // Atom preview rotation in palette
        uiGroup.children.forEach(child => {
            if (child.userData?.type === 'atom-preview') {
                child.rotation.y += delta * 0.8;
                child.rotation.x += delta * 0.3;
            }
        });

        if (!cursorData || !camera || !cursorData.visible) {
            if (hoveredElement) {
                resetHoverState(hoveredElement);
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

        // Reset previous hover
        if (hoveredElement && (!intersects.length || intersects[0].object !== hoveredElement)) {
            resetHoverState(hoveredElement);
            hoveredElement = null;
        }

        if (intersects.length > 0) {
            const hit = intersects[0].object;
            hoveredElement = hit;
            applyHoverState(hit);

            if (cursorData.clicking && !hit.userData.justClicked) {
                hit.userData.justClicked = true;
                handleClick(hit);
            }
        }

        if (!cursorData.clicking) {
            interactiveElements.forEach(el => {
                el.userData.justClicked = false;
            });
        }
    };

    function resetHoverState(element) {
        if (element.userData.type === 'atom-button') {
            if (selectedAtom !== element.userData.atomType) {
                element.material.color.setHex(element.userData.baseColor);
            }
            element.scale.setScalar(1);
        } else if (element.userData.type === 'slot') {
            if (!element.userData.occupied) {
                element.material.color.setHex(element.userData.baseColor);
                element.scale.setScalar(1);
            }
        } else if (element.userData.type === 'clear-button') {
            element.material.color.setHex(element.userData.baseColor);
            element.scale.setScalar(1);
        } else if (element.userData.type === 'placed-atom') {
            element.material.emissiveIntensity = element.userData.baseEmissive || 0.15;
            element.scale.setScalar(1);
        }
    }

    function applyHoverState(element) {
        if (element.userData.type === 'atom-button') {
            const brightColor = new THREE.Color(element.userData.baseColor).multiplyScalar(2);
            element.material.color.copy(brightColor);
            element.scale.setScalar(1.05);
        } else if (element.userData.type === 'slot' && !element.userData.occupied) {
            if (selectedAtom) {
                element.material.color.setHex(atomData[selectedAtom].color);
                if (element.userData.core) {
                    element.userData.core.material.color.setHex(atomData[selectedAtom].color);
                }
                element.scale.setScalar(1.3);
            } else {
                element.material.color.setHex(0x6366f1);
                element.scale.setScalar(1.15);
            }
        } else if (element.userData.type === 'clear-button') {
            element.material.color.setHex(0xef4444);
            element.scale.setScalar(1.05);
        } else if (element.userData.type === 'placed-atom') {
            // Highlight atom on hover (can click to remove)
            element.material.emissiveIntensity = 0.5;
            element.scale.setScalar(1.15);
        }
    }

    function handleClick(element) {
        if (element.userData.type === 'atom-button') {
            // Select this atom type
            selectedAtom = element.userData.atomType;

            // Update button visuals
            interactiveElements.forEach(el => {
                if (el.userData.type === 'atom-button') {
                    if (el.userData.atomType === selectedAtom) {
                        el.material.color.setHex(el.userData.selectedColor);
                    } else {
                        el.material.color.setHex(el.userData.baseColor);
                    }
                }
            });

            // Update selection indicator at current selection
            selectionIndicator.visible = true;

        } else if (element.userData.type === 'slot' && !element.userData.occupied && selectedAtom) {
            // Place atom in slot
            const newAtom = createAtomMesh(selectedAtom, element.position.clone());
            newAtom.userData.slotRef = element; // Store reference to slot for removal
            newAtom.userData.baseEmissive = atomData[selectedAtom].emissiveIntensity || 0.15;
            placedAtoms.push(newAtom);
            interactiveElements.push(newAtom); // Add to interactive for click-to-remove
            moleculeGroup.add(newAtom);

            element.userData.occupied = true;
            element.visible = false;

            updateBonds();

        } else if (element.userData.type === 'placed-atom') {
            // Remove atom by clicking on it
            const slotRef = element.userData.slotRef;
            if (slotRef) {
                slotRef.userData.occupied = false;
                slotRef.visible = true;
                slotRef.material.color.setHex(0x6366f1);
                if (slotRef.userData.core) {
                    slotRef.userData.core.material.color.setHex(0x6366f1);
                }
            }

            // Remove from arrays
            const atomIdx = placedAtoms.indexOf(element);
            if (atomIdx > -1) placedAtoms.splice(atomIdx, 1);
            const interIdx = interactiveElements.indexOf(element);
            if (interIdx > -1) interactiveElements.splice(interIdx, 1);

            moleculeGroup.remove(element);
            updateBonds();

        } else if (element.userData.type === 'clear-button') {
            clearMolecule();
            selectedAtom = null;
            selectionIndicator.visible = false;

            // Reset all button colors
            interactiveElements.forEach(el => {
                if (el.userData.type === 'atom-button') {
                    el.material.color.setHex(el.userData.baseColor);
                }
            });
        }
    }

    // Preset molecules for quick loading
    const presets = {
        water: [
            { type: 'O', slot: 0 },
            { type: 'H', slot: 3 },
            { type: 'H', slot: 4 }
        ],
        methane: [
            { type: 'C', slot: 0 },
            { type: 'H', slot: 1 },
            { type: 'H', slot: 2 },
            { type: 'H', slot: 3 },
            { type: 'H', slot: 5 }
        ],
        co2: [
            { type: 'C', slot: 0 },
            { type: 'O', slot: 1 },
            { type: 'O', slot: 2 }
        ]
    };

    return {
        scene,
        update,
        defaultDistance: 12,
        minDistance: 5,
        maxDistance: 25,
        isInteractive: true
    };
}
