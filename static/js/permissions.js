(function() {
    'use strict';

    function initPermissions() {
        console.log('[FitStack] Initializing Permissions System...');

    // -------------------------------------------------------------------------
    // 1. DOM Elements
    // -------------------------------------------------------------------------
    const permCounterEl = document.getElementById('selected-perm-count');
    const permSearchInput = document.getElementById('perm-search-input');
    const permTable = document.getElementById('perm-matrix-table');
    const allCheckboxes = document.querySelectorAll('.perm-checkbox');
    const roleSelect = document.getElementById('id_role_select');
    const roleBadge = document.getElementById('role-badge-preview');
    const roleDesc = document.getElementById('role-desc-preview');

    const passwordInput = document.getElementById('id_password');
    const confirmPasswordInput = document.getElementById('id_confirm_password');
    const togglePasswordBtn = document.getElementById('toggle-password-btn');
    const toggleConfirmBtn = document.getElementById('toggle-confirm-password-btn');
    const meterSegments = document.querySelectorAll('.meter-segment');
    const meterText = document.getElementById('password-meter-text');
    const passwordMatchHint = document.getElementById('password-match-hint');

    const photoInput = document.getElementById('id_photo');
    const photoPreviewContainer = document.getElementById('preview_id_photo');
    const defaultAvatarSrc = photoPreviewContainer ? photoPreviewContainer.getAttribute('data-default-avatar') : '';
    const resetPhotoBtn = document.getElementById('reset-photo-btn');

    // -------------------------------------------------------------------------
    // 2. Permission Counter & Column Checkbox State
    // -------------------------------------------------------------------------
    function updatePermissionStats() {
        const checkedBoxes = document.querySelectorAll('.perm-checkbox:checked');
        const totalBoxes = allCheckboxes.length;
        if (permCounterEl) {
            permCounterEl.textContent = `${checkedBoxes.length} / ${totalBoxes} Permissions Selected`;
            if (checkedBoxes.length > 0) {
                permCounterEl.className = 'badge badge-soft-primary px-3 py-2';
            } else {
                permCounterEl.className = 'badge badge-soft-secondary px-3 py-2';
            }
        }

        // Update column headers (Select-All View, Add, Change, Delete)
        ['view', 'add', 'change', 'delete'].forEach(permType => {
            const colBoxes = Array.from(document.querySelectorAll(`.${permType}-perm`));
            const colHeader = document.getElementById(`select-all-${permType}`);
            if (colHeader && colBoxes.length > 0) {
                const checkedColBoxes = colBoxes.filter(cb => cb.checked);
                if (checkedColBoxes.length === 0) {
                    colHeader.checked = false;
                    colHeader.indeterminate = false;
                } else if (checkedColBoxes.length === colBoxes.length) {
                    colHeader.checked = true;
                    colHeader.indeterminate = false;
                } else {
                    colHeader.checked = false;
                    colHeader.indeterminate = true;
                }
            }
        });

        // Update row switches
        const rows = document.querySelectorAll('#perm-matrix-table tbody tr');
        rows.forEach(row => {
            const rowBoxes = Array.from(row.querySelectorAll('.perm-checkbox'));
            const rowBtn = row.querySelector('.row-switch-btn');
            if (rowBtn && rowBoxes.length > 0) {
                const allChecked = rowBoxes.every(cb => cb.checked);
                const someChecked = rowBoxes.some(cb => cb.checked);
                if (allChecked) {
                    rowBtn.classList.add('active');
                    rowBtn.textContent = 'All Set';
                } else if (someChecked) {
                    rowBtn.classList.remove('active');
                    rowBtn.textContent = 'Partial';
                } else {
                    rowBtn.classList.remove('active');
                    rowBtn.textContent = 'Select All';
                }
            }
        });
    }

    // -------------------------------------------------------------------------
    // 3. Smart Dependency Logic (View is required for Add/Change/Delete)
    // -------------------------------------------------------------------------
    document.addEventListener('change', function(e) {
        if (!e.target.classList.contains('perm-checkbox')) return;

        const cb = e.target;
        const row = cb.closest('tr');
        if (!row) return;

        const viewCb = row.querySelector('.view-perm');
        const addCb = row.querySelector('.add-perm');
        const changeCb = row.querySelector('.change-perm');
        const deleteCb = row.querySelector('.delete-perm');

        if (cb === viewCb && !cb.checked) {
            // Unchecking View unchecks all others in that row
            if (addCb) addCb.checked = false;
            if (changeCb) changeCb.checked = false;
            if (deleteCb) deleteCb.checked = false;
        } else if (cb !== viewCb && cb.checked) {
            // Checking Add, Change, or Delete automatically enables View
            if (viewCb && !viewCb.checked) {
                viewCb.checked = true;
            }
        }

        updatePermissionStats();
    });

    // -------------------------------------------------------------------------
    // 4. Column Select-All Handlers
    // -------------------------------------------------------------------------
    ['view', 'add', 'change', 'delete'].forEach(permType => {
        const headerCb = document.getElementById(`select-all-${permType}`);
        if (headerCb) {
            headerCb.addEventListener('change', function() {
                const isChecked = this.checked;
                const colBoxes = document.querySelectorAll(`.${permType}-perm`);
                colBoxes.forEach(box => {
                    // Only apply if parent row is not hidden by search
                    const row = box.closest('tr');
                    if (row && row.style.display !== 'none') {
                        box.checked = isChecked;
                        if (isChecked && permType !== 'view') {
                            const viewCb = row.querySelector('.view-perm');
                            if (viewCb) viewCb.checked = true;
                        }
                    }
                });

                if (!isChecked && permType === 'view') {
                    // Unchecking all View unchecks everything else
                    allCheckboxes.forEach(box => {
                        const row = box.closest('tr');
                        if (row && row.style.display !== 'none') {
                            box.checked = false;
                        }
                    });
                }

                updatePermissionStats();
            });
        }
    });

    // -------------------------------------------------------------------------
    // 5. Row-level Toggle Handlers
    // -------------------------------------------------------------------------
    document.addEventListener('click', function(e) {
        const btn = e.target.closest('.row-switch-btn');
        if (btn) {
            const row = btn.closest('tr');
            if (row) {
                const rowBoxes = Array.from(row.querySelectorAll('.perm-checkbox'));
                const allChecked = rowBoxes.every(cb => cb.checked);
                rowBoxes.forEach(cb => {
                    cb.checked = !allChecked;
                });
                updatePermissionStats();
            }
        }
    });

    // -------------------------------------------------------------------------
    // 6. Preset Role Configurations (1-Click & Dropdown Auto-Application)
    // -------------------------------------------------------------------------
    function setModulePerms(spec) {
        allCheckboxes.forEach(cb => cb.checked = false);
        Object.entries(spec).forEach(([key, perms]) => {
            let selector = '';
            if (key.includes(':')) {
                const [app, model] = key.split(':');
                selector = `tr[data-app="${app}"][data-model="${model}"]`;
            } else {
                selector = `tr[data-app="${key}"]`;
            }
            const rows = document.querySelectorAll(selector);
            rows.forEach(row => {
                perms.forEach(permType => {
                    const cb = row.querySelector(`.${permType}-perm`);
                    if (cb) cb.checked = true;
                });
            });
        });
    }

    const PRESET_MAP = {
        'full-admin': () => {
            allCheckboxes.forEach(cb => cb.checked = true);
        },
        'subadmin': () => {
            setModulePerms({
                'enquiry': ['view', 'add', 'change'],
                'members': ['view', 'add', 'change'],
                'trainers': ['view', 'add', 'change'],
                'attendance': ['view', 'add', 'change'],
                'billing': ['view', 'add', 'change'],
                'expenses': ['view'],
                'inventory': ['view', 'add', 'change'],
                'events': ['view', 'add', 'change'],
                'management:membershipplan': ['view', 'add', 'change'],
                'management:dietplan': ['view', 'add', 'change'],
                'management:workoutplan': ['view', 'add', 'change'],
                'settings': ['view']
            });
        },
        'manager': () => {
            allCheckboxes.forEach(cb => cb.checked = false);
            document.querySelectorAll('tr:not([data-app="settings"]) .view-perm, tr:not([data-app="settings"]) .add-perm, tr:not([data-app="settings"]) .change-perm').forEach(cb => cb.checked = true);
            const settingsView = document.querySelector('tr[data-app="settings"] .view-perm');
            if (settingsView) settingsView.checked = true;
        },
        'front-desk': () => {
            setModulePerms({
                'enquiry': ['view', 'add', 'change'],
                'members': ['view', 'add', 'change'],
                'trainers': ['view'],
                'attendance': ['view', 'add', 'change'],
                'billing': ['view', 'add', 'change'],
                'events': ['view', 'add'],
                'management:membershipplan': ['view']
            });
        },
        'trainer': () => {
            setModulePerms({
                'members': ['view'],
                'attendance': ['view', 'add'],
                'events': ['view'],
                'management:membershipplan': ['view'],
                'management:dietplan': ['view', 'add', 'change'],
                'management:workoutplan': ['view', 'add', 'change']
            });
        },
        'accounts': () => {
            setModulePerms({
                'billing': ['view', 'add', 'change', 'delete'],
                'expenses': ['view', 'add', 'change', 'delete'],
                'members': ['view'],
                'management:membershipplan': ['view']
            });
        },
        'inventory': () => {
            setModulePerms({
                'inventory': ['view', 'add', 'change', 'delete'],
                'expenses': ['view', 'add']
            });
        },
        'marketing': () => {
            setModulePerms({
                'enquiry': ['view', 'add', 'change', 'delete'],
                'members': ['view'],
                'events': ['view', 'add', 'change']
            });
        },
        'view-only': () => {
            allCheckboxes.forEach(cb => cb.checked = false);
            document.querySelectorAll('.view-perm').forEach(cb => cb.checked = true);
        },
        'clear-all': () => {
            allCheckboxes.forEach(cb => cb.checked = false);
        }
    };

    function applyPreset(presetKey, presetName) {
        if (PRESET_MAP[presetKey]) {
            PRESET_MAP[presetKey]();
            updatePermissionStats();

            // Button visual feedback
            document.querySelectorAll('.btn-preset').forEach(b => b.classList.remove('active'));
            const matchingBtn = document.querySelector(`.btn-preset[data-preset="${presetKey}"]`);
            if (matchingBtn) {
                matchingBtn.classList.add('active');
                setTimeout(() => {
                    matchingBtn.classList.remove('active');
                }, 1200);
            }

            // Indicator feedback
            const presetIndicator = document.getElementById('preset-applied-indicator');
            const presetNameEl = document.getElementById('preset-applied-name');
            if (presetIndicator && presetName) {
                if (presetNameEl) presetNameEl.textContent = presetName;
                presetIndicator.style.display = 'inline-flex';
                setTimeout(() => {
                    if (presetIndicator) presetIndicator.style.display = 'none';
                }, 4000);
            }
        }
    }

    document.querySelectorAll('.btn-preset').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const presetKey = this.getAttribute('data-preset');
            const btnText = this.textContent.trim();
            applyPreset(presetKey, btnText);
        });
    });

    // -------------------------------------------------------------------------
    // 7. Live Module Search Filter
    // -------------------------------------------------------------------------
    if (permSearchInput && permTable) {
        permSearchInput.addEventListener('input', function() {
            const query = this.value.trim().toLowerCase();
            const rows = permTable.querySelectorAll('tbody tr');
            let visibleCount = 0;

            rows.forEach(row => {
                const title = (row.querySelector('.perm-module-title') || {}).textContent || '';
                const desc = (row.querySelector('.perm-module-desc') || {}).textContent || '';
                const app = row.getAttribute('data-app') || '';
                const match = title.toLowerCase().includes(query) || 
                              desc.toLowerCase().includes(query) || 
                              app.toLowerCase().includes(query);

                row.style.display = match ? '' : 'none';
                if (match) visibleCount++;
            });

            // If no match found, show clean message row
            let noMatchRow = document.getElementById('perm-no-match-row');
            if (visibleCount === 0) {
                if (!noMatchRow) {
                    noMatchRow = document.createElement('tr');
                    noMatchRow.id = 'perm-no-match-row';
                    noMatchRow.innerHTML = `
                        <td colspan="6" class="text-center py-4 text-muted">
                            <i class="mdi mdi-filter-remove-outline mdi-24px mb-2 d-block text-secondary"></i>
                            No modules found matching "<strong>${query}</strong>"
                        </td>
                    `;
                    permTable.querySelector('tbody').appendChild(noMatchRow);
                }
            } else if (noMatchRow) {
                noMatchRow.remove();
            }
        });
    }

    // -------------------------------------------------------------------------
    // 8. Dynamic Role Selection Helpers (No emojis, standard MDI icons)
    // -------------------------------------------------------------------------
    const ROLE_INFO = {
        'admin': {
            badge: '<i class="mdi mdi-shield-crown-outline me-1"></i> Full Administrator',
            class: 'badge-soft-primary',
            desc: 'Full operational authority across all gym modules and management.',
            preset: 'full-admin',
            presetName: 'Full Admin'
        },
        'subadmin': {
            badge: '<i class="mdi mdi-shield-account-outline me-1"></i> Sub-Admin',
            class: 'badge-soft-info',
            desc: 'Branch operational staff with custom module permissions.',
            preset: 'subadmin',
            presetName: 'Sub-Admin'
        },
        'front_desk': {
            badge: '<i class="mdi mdi-desk me-1"></i> Front Desk & Reception',
            class: 'badge-soft-success',
            desc: 'Handles member inquiries, daily check-ins, registrations, and billing.',
            preset: 'front-desk',
            presetName: 'Front Desk'
        },
        'trainer': {
            badge: '<i class="mdi mdi-dumbbell me-1"></i> Fitness Trainer',
            class: 'badge-soft-warning',
            desc: 'Manages member training attendance, workout routines, and diet progress.',
            preset: 'trainer',
            presetName: 'Trainer'
        },
        'manager': {
            badge: '<i class="mdi mdi-briefcase-account-outline me-1"></i> Branch Manager',
            class: 'badge-soft-primary',
            desc: 'Oversees daily gym operations, staff shifts, members, and facilities.',
            preset: 'manager',
            presetName: 'Manager'
        },
        'accounts': {
            badge: '<i class="mdi mdi-cash-multiple me-1"></i> Accounts & Finance',
            class: 'badge-soft-success',
            desc: 'Manages payments, fee renewals, member invoicing, and expenses.',
            preset: 'accounts',
            presetName: 'Accounts'
        },
        'inventory': {
            badge: '<i class="mdi mdi-package-variant-closed me-1"></i> Inventory Specialist',
            class: 'badge-soft-primary',
            desc: 'Monitors equipment status, maintenance cycles, and supplement stocks.',
            preset: 'inventory',
            presetName: 'Inventory'
        },
        'marketing': {
            badge: '<i class="mdi mdi-bullhorn-outline me-1"></i> Marketing / CRM',
            class: 'badge-soft-info',
            desc: 'Manages incoming inquiries, walk-ins, follow-up calls, and conversion.',
            preset: 'marketing',
            presetName: 'Marketing'
        }
    };

    function updateRoleDisplay(role, applyPresetAutomatically = false) {
        if (role && ROLE_INFO[role]) {
            const info = ROLE_INFO[role];
            if (roleBadge) {
                roleBadge.innerHTML = info.badge;
                roleBadge.className = `role-badge-preview ${info.class}`;
                roleBadge.style.display = 'inline-flex';
            }
            if (roleDesc) {
                roleDesc.textContent = info.desc;
            }

            if (applyPresetAutomatically && info.preset) {
                applyPreset(info.preset, info.presetName);
            }
        } else {
            if (roleBadge) {
                roleBadge.style.display = 'none';
            }
            if (roleDesc) {
                roleDesc.textContent = 'Select a designated staff role for this sub-admin account.';
            }
        }
    }

    if (roleSelect) {
        // When Designated Role dropdown changes -> automatically apply corresponding Quick Preset
        roleSelect.addEventListener('change', function() {
            updateRoleDisplay(this.value, true);
        });

        // Initial check on load (show badge preview, and auto-apply preset if brand new form with 0 checked boxes)
        if (roleSelect.value) {
            const hasExistingChecks = document.querySelectorAll('.perm-checkbox:checked').length > 0;
            // If already has checks (e.g. edit mode), don't overwrite on initial load; only update badge
            updateRoleDisplay(roleSelect.value, !hasExistingChecks);
        }
    }

    // -------------------------------------------------------------------------
    // 9. Password Strength Meter & Visibility Toggles
    // -------------------------------------------------------------------------
    function evaluatePasswordStrength(pass) {
        let score = 0;
        if (!pass) return 0;
        if (pass.length >= 6) score++;
        if (pass.length >= 9) score++;
        if (/[A-Z]/.test(pass) && /[a-z]/.test(pass)) score++;
        if (/[0-9]/.test(pass) && /[^A-Za-z0-9]/.test(pass)) score++;
        return score; // 0 to 4
    }

    if (passwordInput) {
        passwordInput.addEventListener('input', function() {
            const val = this.value;
            const score = evaluatePasswordStrength(val);

            meterSegments.forEach((seg, idx) => {
                if (idx < score) {
                    if (score === 1) seg.style.background = '#ef4444'; // red
                    else if (score === 2) seg.style.background = '#f59e0b'; // orange
                    else if (score === 3) seg.style.background = '#3b82f6'; // blue
                    else seg.style.background = '#10b981'; // green
                } else {
                    seg.style.background = '#e2e8f0';
                }
            });

            if (meterText) {
                const labels = ['Enter password', 'Weak (add numbers/symbols)', 'Fair', 'Good', 'Strong & Secure'];
                meterText.textContent = labels[score];
                meterText.style.color = score >= 3 ? '#10b981' : (score === 2 ? '#f59e0b' : '#64748b');
            }

            checkPasswordMatch();
        });
    }

    function checkPasswordMatch() {
        if (!confirmPasswordInput || !passwordInput) return;
        const p1 = passwordInput.value;
        const p2 = confirmPasswordInput.value;

        if (!p2) {
            if (passwordMatchHint) passwordMatchHint.textContent = '';
            confirmPasswordInput.closest('.input-group-modern')?.classList.remove('is-invalid');
            return;
        }

        if (p1 === p2) {
            if (passwordMatchHint) {
                passwordMatchHint.innerHTML = '<span class="text-success"><i class="mdi mdi-check-circle"></i> Passwords match</span>';
            }
            confirmPasswordInput.closest('.input-group-modern')?.classList.remove('is-invalid');
        } else {
            if (passwordMatchHint) {
                passwordMatchHint.innerHTML = '<span class="text-danger"><i class="mdi mdi-alert-circle"></i> Passwords do not match</span>';
            }
            confirmPasswordInput.closest('.input-group-modern')?.classList.add('is-invalid');
        }
    }

    if (confirmPasswordInput) {
        confirmPasswordInput.addEventListener('input', checkPasswordMatch);
    }

    function setupPasswordToggle(btn, input) {
        if (!btn || !input) return;
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const icon = this.querySelector('i');
            if (input.type === 'password') {
                input.type = 'text';
                if (icon) {
                    icon.classList.remove('mdi-eye-outline');
                    icon.classList.add('mdi-eye-off-outline');
                }
            } else {
                input.type = 'password';
                if (icon) {
                    icon.classList.remove('mdi-eye-off-outline');
                    icon.classList.add('mdi-eye-outline');
                }
            }
        });
    }

    setupPasswordToggle(togglePasswordBtn, passwordInput);
    setupPasswordToggle(toggleConfirmBtn, confirmPasswordInput);

    // -------------------------------------------------------------------------
    // 10. Photo Preview & Reset Handler
    // -------------------------------------------------------------------------
    if (photoInput && photoPreviewContainer) {
        photoInput.addEventListener('change', function() {
            if (this.files && this.files[0]) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    const img = photoPreviewContainer.querySelector('img');
                    if (img) img.src = e.target.result;
                    photoPreviewContainer.style.display = 'block';
                };
                reader.readAsDataURL(this.files[0]);
            }
        });
    }

    if (resetPhotoBtn && photoInput && photoPreviewContainer) {
        resetPhotoBtn.addEventListener('click', function(e) {
            e.preventDefault();
            photoInput.value = '';
            const img = photoPreviewContainer.querySelector('img');
            if (img && defaultAvatarSrc) {
                img.src = defaultAvatarSrc;
            }
        });
    }

    // -------------------------------------------------------------------------
    // 11. Initial Run
    // -------------------------------------------------------------------------
    updatePermissionStats();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initPermissions);
    } else {
        initPermissions();
    }
})();