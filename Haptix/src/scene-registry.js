/**
 * SceneRegistry — dynamic scene discovery and dropdown generation.
 * Uses import.meta.glob to auto-discover all scene files.
 */

export class SceneRegistry {
    constructor() {
        this._scenes = new Map();
    }

    register(id, metadata, factory) {
        this._scenes.set(id, { id, metadata, factory });
    }

    get(id) {
        return this._scenes.get(id);
    }

    getAll() {
        return Array.from(this._scenes.values());
    }

    getByCategory(category) {
        return this.getAll().filter(s => s.metadata.category === category);
    }

    getCategories() {
        const cats = new Set();
        for (const scene of this._scenes.values()) {
            if (scene.metadata.category) cats.add(scene.metadata.category);
        }
        return Array.from(cats);
    }

    async discoverScenes() {
        const modules = import.meta.glob('./scenes/*.js', { eager: true });

        for (const [path, mod] of Object.entries(modules)) {
            const filename = path.split('/').pop().replace('.js', '');
            const metadata = mod.metadata || { name: filename, category: 'Other', description: '', interactive: false };
            const factory = mod.default || null;

            if (factory) {
                this.register(filename, metadata, factory);
            }
        }
    }

    buildDropdown(container) {
        container.innerHTML = '';

        const categories = this.getCategories();
        for (const category of categories) {
            const section = document.createElement('div');
            section.className = 'dropdown-section';

            const label = document.createElement('div');
            label.className = 'dropdown-label';
            label.textContent = category;
            section.appendChild(label);

            const scenes = this.getByCategory(category);
            for (const scene of scenes) {
                const btn = document.createElement('button');
                btn.className = 'dropdown-item';
                btn.dataset.scene = scene.id;
                btn.textContent = scene.metadata.name;
                if (scene.metadata.description) {
                    btn.title = scene.metadata.description;
                }
                section.appendChild(btn);
            }

            container.appendChild(section);
        }

        // Add upload divider + button
        const divider = document.createElement('div');
        divider.className = 'dropdown-divider';
        container.appendChild(divider);

        const uploadBtn = document.createElement('button');
        uploadBtn.className = 'dropdown-item upload-item';
        uploadBtn.id = 'upload-btn';
        uploadBtn.innerHTML = `
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
            Upload Model
        `;
        container.appendChild(uploadBtn);
    }
}
