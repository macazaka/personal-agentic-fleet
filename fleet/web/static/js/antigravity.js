// --- Antigravity Live Stream, Models & Agent Control ---
let lastRenderedStep = -1;
let attachedImages = [];
let activeModelId = 'gemini-3.8-flash-high';
let availableModels = [];

    async function fetchTranscript(forceScroll = false) {
      try {
        const res = await fetch('/api/antigravity/transcript?limit=80');
        const data = await res.json();
        if (data.status !== 'success') return;

        const sessionBadge = document.getElementById('agSessionBadge');
        if (sessionBadge && data.session_id) {
          sessionBadge.innerText = 'Session: ' + data.session_id.substring(0, 8);
        }
        const countBadge = document.getElementById('agMsgCountBadge');
        if (countBadge) {
          countBadge.innerText = `${data.messages.length} Steps`;
        }

        const container = document.getElementById('agChatScroll');
        if (!container) return;

        if (data.messages.length === 0) {
          container.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 40px;">No messages in transcript yet.</div>';
          return;
        }

        if (data.latest_step === lastRenderedStep && !forceScroll) {
          return;
        }
        lastRenderedStep = data.latest_step;

        const html = data.messages.map(m => {
          let mediaHtml = '';
          if (m.media && m.media.length > 0) {
            mediaHtml = '<div class="ag-msg-media">' + m.media.map(med => `
              <img src="${escapeHtml(med.url)}" title="${escapeHtml(med.name || 'Image')}" onclick="openImageLightbox('${escapeHtml(med.url)}')">
            `).join('') + '</div>';
          }

          if (m.role === 'user') {
            return `
              <div class="ag-message ag-msg-user">
                <div class="ag-msg-role">👤 User</div>
                <div>${formatMarkdown(m.text)}</div>
                ${mediaHtml}
              </div>
            `;
          } else {
            let thinkingHtml = '';
            if (m.thinking) {
              thinkingHtml = `
                <details class="ag-thinking">
                  <summary>🧠 Thinking Process <span style="font-size:10.5px; opacity:0.7;">(Click to view reasoning)</span></summary>
                  <div class="ag-thinking-body">${escapeHtml(m.thinking)}</div>
                </details>
              `;
            }

            let toolsHtml = '';
            if (m.tools && m.tools.length > 0) {
              toolsHtml = '<div class="ag-tools-group">' + m.tools.map(t => `
                <div class="ag-tool-card">
                  <span class="name">⚡ ${escapeHtml(t.name)}</span>
                  <span class="desc">${escapeHtml(t.summary)}</span>
                </div>
              `).join('') + '</div>';
            }

            return `
              <div class="ag-message ag-msg-assistant">
                <div class="ag-msg-role">🤖 Antigravity 2.0</div>
                ${thinkingHtml}
                ${toolsHtml}
                <div>${formatMarkdown(m.text)}</div>
                ${mediaHtml}
              </div>
            `;
          }
        }).join('');

        container.innerHTML = html;

        const autoScroll = document.getElementById('autoScrollCheck');
        if (autoScroll && autoScroll.checked) {
          container.scrollTop = container.scrollHeight;
        }
      } catch (e) {
        console.error('Transcript fetch error:', e);
      }
    }

    function fillCommand(cmd) {
      const input = document.getElementById('agCommandInput');
      if (input) {
        input.value = cmd;
        if (input.tagName && input.tagName.toLowerCase() === 'textarea') {
          input.style.height = 'auto';
          input.style.height = Math.min(Math.max(input.scrollHeight, 60), 180) + 'px';
        }
        input.focus();
      }
    }

    // --- Image Upload, Paste & Drag-and-Drop ---
    function uploadImageBlob(file, customName) {
      const reader = new FileReader();
      reader.onload = async function(e) {
        const base64Data = e.target.result;
        try {
          const res = await fetch('/api/antigravity/upload', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
              filename: customName || file.name || `image_${Date.now()}.png`,
              data: base64Data
            })
          });
          const json = await res.json();
          if (json.status === 'success' && json.file) {
            attachedImages.push(json.file);
            renderAttachmentStrip();
          }
        } catch (err) {
          console.error('Error uploading image:', err);
        }
      };
      reader.readAsDataURL(file);
    }

    function handleImageFileSelect(event) {
      const files = event.target.files;
      if (!files) return;
      for (let i = 0; i < files.length; i++) {
        uploadImageBlob(files[i], files[i].name);
      }
      event.target.value = '';
    }

    function renderAttachmentStrip() {
      const strip = document.getElementById('agAttachmentStrip');
      if (!strip) return;
      if (attachedImages.length === 0) {
        strip.style.display = 'none';
        strip.innerHTML = '';
        return;
      }
      strip.style.display = 'flex';
      strip.innerHTML = attachedImages.map((img, idx) => `
        <div class="ag-attach-thumb" title="${escapeHtml(img.filename)}">
          <img src="${escapeHtml(img.url)}" onclick="openImageLightbox('${escapeHtml(img.url)}')">
          <div class="remove-btn" onclick="removeAttachment(${idx})">✕</div>
        </div>
      `).join('');
    }

    function removeAttachment(idx) {
      attachedImages.splice(idx, 1);
      renderAttachmentStrip();
    }

    function openImageLightbox(src) {
      const modal = document.getElementById('imageLightboxModal');
      const img = document.getElementById('lightboxImg');
      if (modal && img) {
        img.src = src;
        modal.style.display = 'flex';
      }
    }

    function closeImageLightbox() {
      const modal = document.getElementById('imageLightboxModal');
      if (modal) modal.style.display = 'none';
    }

    // Attach paste listener to window
    window.addEventListener('paste', (e) => {
      if (!e.clipboardData || !e.clipboardData.items) return;
      const items = e.clipboardData.items;
      for (let i = 0; i < items.length; i++) {
        if (items[i].type && items[i].type.indexOf('image') !== -1) {
          const file = items[i].getAsFile();
          if (file) {
            uploadImageBlob(file, `pasted_image_${Date.now()}.png`);
            e.preventDefault();
          }
        }
      }
    });

    // Attach drag & drop listeners to console container & scroll area
    setTimeout(() => {
      ['agConsoleContainer', 'agChatScroll'].forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        el.addEventListener('dragover', (e) => {
          e.preventDefault();
          el.classList.add('ag-drag-over');
        });
        el.addEventListener('dragleave', (e) => {
          e.preventDefault();
          el.classList.remove('ag-drag-over');
        });
        el.addEventListener('drop', (e) => {
          e.preventDefault();
          el.classList.remove('ag-drag-over');
          if (e.dataTransfer && e.dataTransfer.files) {
            for (let i = 0; i < e.dataTransfer.files.length; i++) {
              const file = e.dataTransfer.files[i];
              if (file.type && file.type.startsWith('image/')) {
                uploadImageBlob(file, file.name);
              }
            }
          }
        });
      });

      const cmdInput = document.getElementById('agCommandInput');
      if (cmdInput && cmdInput.tagName && cmdInput.tagName.toLowerCase() === 'textarea') {
        cmdInput.addEventListener('input', function() {
          this.style.height = 'auto';
          this.style.height = Math.min(Math.max(this.scrollHeight, 60), 180) + 'px';
        });
      }
    }, 500);

    // --- Model Selector & Usage Details ---
    function formatActiveModelButtonLabel(modelObj) {
      if (!modelObj) return 'Gemini 3.8 Flash (High)';
      const baseName = (modelObj.name || '').trim();
      const effort = (modelObj.effort || '').trim();
      if (!effort || baseName.toLowerCase().includes(effort.toLowerCase())) {
        return baseName;
      }
      return `${baseName} (${effort})`;
    }

    async function fetchModels() {
      try {
        const res = await fetch('/api/antigravity/models');
        const data = await res.json();
        availableModels = data.models || [];
        activeModelId = data.active_model || 'gemini-3.8-flash-high';
        
        const activeObj = availableModels.find(m => m.id === activeModelId) || availableModels[0];
        const labelText = formatActiveModelButtonLabel(activeObj);
        const labelEl = document.getElementById('agActiveModelLabel');
        if (labelEl) labelEl.innerText = labelText;

        const datalist = document.getElementById('antigravityModelsDatalist');
        if (datalist) {
          datalist.innerHTML = availableModels
            .filter(m => m.available && !m.hidden_in_menu)
            .map(m => `<option value="${escapeHtml(m.id)}">${escapeHtml(m.name)}</option>`)
            .join('');
        }

        const list = document.getElementById('agModelOptionsList');
        if (list) {
          const visibleModels = availableModels.filter(m => !m.hidden_in_menu || m.id === activeModelId);
          let currentGroup = '';
          const rows = [];
          visibleModels.forEach(m => {
            const groupName = m.group || (m.source === 'antigravity' ? 'Antigravity Live Models' : 'Cloud Hyperscalers & Dev Tools');
            if (groupName !== currentGroup) {
              currentGroup = groupName;
              const groupIcon = groupName.toLowerCase().includes('antigravity') ? '⚡' : '☁️';
              rows.push(`<div class="ag-model-group-header">${groupIcon} ${escapeHtml(groupName)}</div>`);
            }
            const isSelected = m.id === activeModelId;
            const isDis = !m.available;
            const check = isSelected ? '<span style="color:var(--accent-cyan); font-weight:bold; margin-right:6px;">✓</span>' : '<span style="display:inline-block; width:14px; margin-right:6px;"></span>';
            const badgeClass = m.badge_color || 'gray';
            const tip = m.description ? `${m.name} (${m.id}) — ${m.description}` : `${m.name} (${m.id})`;
            rows.push(`
              <div class="ag-model-menu-item ${isSelected ? 'active' : ''} ${isDis ? 'disabled' : ''}" title="${escapeHtml(tip)}" onclick="selectModel('${m.id}', ${isDis ? 'true' : 'false'})">
                <div style="display:flex; align-items:center;">
                  ${check}
                  <span>${escapeHtml(m.name)}</span>
                </div>
                <div>
                  <span class="ag-pill-badge ${badgeClass}">${escapeHtml(m.badge || m.effort || '')}</span>
                </div>
              </div>
            `);
          });
          list.innerHTML = rows.join('');
        }
      } catch (e) {
        console.error('Error fetching models:', e);
      }
    }

    function toggleModelMenu(e) {
      if (e) e.stopPropagation();
      const menu = document.getElementById('agModelMenu');
      const btn = document.getElementById('agModelDropdownBtn');
      if (!menu) return;
      
      const isOpen = menu.style.display === 'block';
      if (isOpen) {
        menu.style.display = 'none';
        return;
      }

      menu.style.display = 'block';

      // Smart viewport boundary adjustment so the menu is never cut off
      if (btn) {
        const btnRect = btn.getBoundingClientRect();
        const spaceAbove = btnRect.top;
        const list = document.getElementById('agModelOptionsList');
        if (list) {
          if (spaceAbove < 390) {
            list.style.maxHeight = Math.max(140, Math.floor(spaceAbove - 70)) + 'px';
          } else {
            list.style.maxHeight = '320px';
          }
          list.scrollTop = 0;
          const activeEl = list.querySelector('.ag-model-menu-item.active');
          if (activeEl) {
            activeEl.scrollIntoView({ block: 'nearest' });
          }
        }
      }
    }

    async function selectModel(modelId, isDisabled) {
      if (isDisabled) return;
      try {
        const res = await fetch('/api/antigravity/models', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ model: modelId })
        });
        const data = await res.json();
        if (data.status === 'success' || data.model) {
          activeModelId = modelId;
          fetchModels();
        }
      } catch (e) {
        console.error('Error selecting model:', e);
      }
      const menu = document.getElementById('agModelMenu');
      if (menu) menu.style.display = 'none';
    }

    window.addEventListener('click', (e) => {
      const menu = document.getElementById('agModelMenu');
      const btn = document.getElementById('agModelDropdownBtn');
      if (menu && menu.style.display === 'block' && !menu.contains(e.target) && !btn.contains(e.target)) {
        menu.style.display = 'none';
      }
    });

    async function openUsageModal() {
      const modal = document.getElementById('usageModal');
      const content = document.getElementById('usageModalContent');
      if (!modal || !content) return;
      modal.style.display = 'flex';
      content.innerHTML = '<div style="color:var(--text-muted); padding:10px;">Loading usage metrics...</div>';
      try {
        const [usageRes, tokenRes, provRes, toolsRes] = await Promise.all([
          fetch('/api/antigravity/usage'),
          fetch('/api/antigravity/tokens'),
          fetch('/api/hyperscalers/providers'),
          fetch('/api/hyperscalers/dev_tools')
        ]);
        if (!usageRes.ok) throw new Error('HTTP ' + usageRes.status + ' loading usage');
        if (!tokenRes.ok) throw new Error('HTTP ' + tokenRes.status + ' loading token health');
        const d = await usageRes.json();
        const t = await tokenRes.json();
        const provData = provRes.ok ? await provRes.json() : { providers: [] };
        const toolsData = toolsRes.ok ? await toolsRes.json() : { tools: {} };
        const provList = provData.providers || [];
        const toolsList = Object.values(toolsData.tools || {});

        const pct = t.percent_used || 0;
        const barColor = t.status === 'exhausted' ? '#ef4444' : (t.status === 'warning' ? '#f59e0b' : 'var(--accent-cyan)');

        content.innerHTML = `
          <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 12px;">
            <div style="background:rgba(0,0,0,0.3); padding:12px; border-radius:8px; border:1px solid var(--card-border);">
              <div style="font-size:11px; color:var(--text-muted);">ACTIVE MODEL</div>
              <div style="font-size:15px; font-weight:700; color:var(--accent-cyan); margin-top:4px;">${escapeHtml(d.active_model)}</div>
              <div style="font-size:11px; color:#a855f7; margin-top:2px;">Effort: ${escapeHtml(d.effort)}</div>
            </div>
            <div style="background:rgba(0,0,0,0.3); padding:12px; border-radius:8px; border:1px solid var(--card-border);">
              <div style="font-size:11px; color:var(--text-muted);">SESSION COST</div>
              <div style="font-size:15px; font-weight:700; color:var(--accent-green); margin-top:4px;">${escapeHtml(d.cost_usd)}</div>
              <div style="font-size:11px; color:var(--text-muted); margin-top:2px;">${escapeHtml(d.tier)}</div>
            </div>
            <div style="background:rgba(0,0,0,0.3); padding:12px; border-radius:8px; border:1px solid var(--card-border);">
              <div style="font-size:11px; color:var(--text-muted);">CONTEXT CAPACITY</div>
              <div style="font-size:15px; font-weight:700; color:#fff; margin-top:4px;">${pct}% Used</div>
              <div style="width:100%; height:6px; background:rgba(255,255,255,0.1); border-radius:3px; margin-top:6px; overflow:hidden;">
                <div style="width:${Math.min(100, pct)}%; height:100%; background:${barColor};"></div>
              </div>
              <div style="font-size:10px; color:var(--text-muted); margin-top:4px;">${(t.tokens_used||0).toLocaleString()} / ${(t.token_limit||0).toLocaleString()} tokens</div>
            </div>
            <div style="background:rgba(0,0,0,0.3); padding:12px; border-radius:8px; border:1px solid var(--card-border);">
              <div style="font-size:11px; color:var(--text-muted);">PRESERVATION VAULT</div>
              <div style="font-size:15px; font-weight:700; color:${t.vaulted_count > 0 ? '#f87171' : 'var(--accent-green)'}; margin-top:4px;">
                ${t.vaulted_count} Vaulted
              </div>
              <div style="font-size:11px; color:var(--text-muted); margin-top:2px;">Status: ${escapeHtml((t.status||'OK').toUpperCase())}</div>
            </div>
          </div>

          <div style="background:rgba(255,255,255,0.02); border:1px solid var(--card-border); border-radius:8px; padding:12px; margin-top:6px;">
            <div style="font-size:11px; font-weight:700; color:var(--text-muted); margin-bottom:8px; text-transform:uppercase; letter-spacing:0.5px;">
              🛡️ Token Exhaustion & Fail-Safe Controls
            </div>
            <div style="display:flex; gap:8px; flex-wrap:wrap;">
              <button class="btn" style="font-size:11.5px; padding:6px 12px;" onclick="openVaultModal()">📦 Open Vault (${t.vaulted_count})</button>
              <button class="btn" style="font-size:11.5px; padding:6px 12px; background:rgba(239,68,68,0.15); border-color:rgba(239,68,68,0.3); color:#fca5a5;" onclick="simulateTokenExhaustion()">⚠️ Simulate Token Exhaustion</button>
              <button class="btn" style="font-size:11.5px; padding:6px 12px; background:rgba(16,185,129,0.15); border-color:rgba(16,185,129,0.3); color:#6ee7b7;" onclick="clearSimulatedTokenExhaustion()">✅ Reset Normal Health</button>
            </div>
          </div>

          <div style="background:rgba(255,255,255,0.02); border:1px solid var(--card-border); border-radius:8px; padding:12px; margin-top:6px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
              <span style="font-size:11px; font-weight:700; color:var(--accent-cyan); text-transform:uppercase; letter-spacing:0.5px;">
                ☁️ Multi-Hyperscaler Gateway & AI Developer Tools
              </span>
              <button class="btn" style="font-size:10.5px; padding:3px 9px;" onclick="syncAllDevToolInstructions()">🔄 Sync Copilot / Claude / Gemini Rules</button>
            </div>
            <div style="display:flex; gap:6px; flex-wrap:wrap; margin-bottom:8px;">
              ${provList.map(p => `<span class="ag-pill-badge ${p.is_configured ? 'green' : 'gray'}" style="font-size:10px;" title="${escapeHtml((p.methods||[]).join(', '))}">${p.is_configured ? '●' : '○'} ${escapeHtml(p.hyperscaler)}</span>`).join('')}
            </div>
            <div style="display:flex; gap:6px; flex-wrap:wrap;">
              ${toolsList.map(tl => `<span class="ag-pill-badge ${tl.installed ? 'blue' : 'purple'}" style="font-size:10px;">${tl.installed ? '✓' : '☁️'} ${escapeHtml(tl.name)}</span>`).join('')}
            </div>
          </div>

          <div style="font-size:11.5px; color:var(--text-muted); margin-top:4px; line-height:1.4;">
            Provider: <strong>${escapeHtml(d.provider)}</strong>.<br>
            Strictly follows Tier 0 computational optimization ($0.00 / 0 Tokens) for all local fleet routines.
          </div>
        `;
      } catch (e) {
        content.innerHTML = `
          <div style="color:#f87171; padding: 6px 0; font-size: 13px;">
            ⚠️ Failed to load usage: ${escapeHtml(e.message)}
          </div>
          <div style="font-size: 11.5px; color: var(--text-muted); margin-bottom: 12px; line-height: 1.4;">
            If the server was momentarily reconnecting, click Retry below.
          </div>
          <button class="btn btn-primary" style="font-size: 11.5px; padding: 6px 14px;" onclick="openUsageModal()">🔄 Retry</button>
        `;
      }
    }

    async function syncAllDevToolInstructions() {
      try {
        const res = await fetch('/api/hyperscalers/dev_tools/sync_all_instructions', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({})
        });
        const data = await res.json();
        const toast = document.getElementById('cmdToast');
        if (toast) {
          toast.style.display = 'block';
          toast.innerText = data.message || 'Synchronized Copilot, Claude Code, and Gemini CLI instructions!';
          setTimeout(() => { toast.style.display = 'none'; }, 4000);
        }
      } catch (e) {
        console.error('Error syncing instructions:', e);
      }
    }

    function closeUsageModal() {
      const modal = document.getElementById('usageModal');
      if (modal) modal.style.display = 'none';
    }

    async function openVaultModal() {
      const modal = document.getElementById('tokenVaultModal');
      const content = document.getElementById('tokenVaultContent');
      if (!modal || !content) return;
      modal.style.display = 'flex';
      content.innerHTML = '<div style="color:var(--text-muted); padding:20px; text-align:center;">Loading vaulted prompts...</div>';
      try {
        const res = await fetch('/api/antigravity/tokens');
        if (!res.ok) throw new Error('HTTP ' + res.status + ' loading tokens');
        const data = await res.json();
        const items = data.vaulted_prompts || [];
        if (items.length === 0) {
          content.innerHTML = `
            <div style="text-align:center; padding:35px 20px; color:var(--text-muted);">
              <div style="font-size:32px; margin-bottom:10px;">✅</div>
              <div style="font-weight:600; color:var(--text); font-size:14px;">Token Vault is Empty</div>
              <div style="font-size:12px; margin-top:4px;">No prompts are currently suspended or waiting for quota replenishment.</div>
            </div>
          `;
          return;
        }
        content.innerHTML = `
          <div style="margin-bottom:12px; font-size:12px; color:var(--accent-cyan);">
            <strong>${items.length} prompt(s) safely vaulted</strong> during token exhaustion:
          </div>
          <div style="display:flex; flex-direction:column; gap:8px;">
            ${items.map(item => `
              <div style="background:rgba(0,0,0,0.3); border:1px solid var(--card-border); border-radius:8px; padding:12px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                  <span class="ag-pill-badge purple" style="font-size:10px;">Queue #${item.id}</span>
                  <span style="font-size:11px; color:var(--text-muted);">${escapeHtml(item.created_at || '')}</span>
                </div>
                <div style="font-size:13px; color:var(--text); line-height:1.4; word-break:break-word;">
                  ${escapeHtml(item.prompt || '(Empty Prompt)')}
                </div>
                <div style="margin-top:8px; display:flex; justify-content:space-between; align-items:center;">
                  <span class="ag-pill-badge gray" style="font-size:10px;">Original Model: ${escapeHtml(item.model || 'Default')}</span>
                  <span style="font-size:11px; color:#f87171; font-weight:600;">Status: Vaulted (Preserved)</span>
                </div>
              </div>
            `).join('')}
          </div>
        `;
      } catch (e) {
        content.innerHTML = `
          <div style="color:#f87171; padding: 6px 0; font-size: 13px;">
            ⚠️ Failed to load vault: ${escapeHtml(e.message)}
          </div>
          <button class="btn btn-primary" style="font-size: 11.5px; padding: 6px 14px; margin-top: 8px;" onclick="openVaultModal()">🔄 Retry</button>
        `;
      }
    }

    function closeVaultModal() {
      const modal = document.getElementById('tokenVaultModal');
      if (modal) modal.style.display = 'none';
    }

    async function resumeVaultedWork() {
      try {
        const healthRes = await fetch('/api/antigravity/tokens');
        const health = await healthRes.json();
        const fallback = health.recommended_fallback || 'gemini-3.8-flash-high';
        
        await fetch('/api/antigravity/tokens/resume', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ fallback_model: fallback })
        });
        closeVaultModal();
        await fetchTokenHealth();
        await fetchAgentQueue();
        await fetchTranscript(true);
      } catch (e) {
        console.error('Error resuming vaulted work:', e);
      }
    }

    async function simulateTokenExhaustion() {
      try {
        await fetch('/api/antigravity/tokens/simulate', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ status: 'exhausted', reason: 'Simulated token quota limit reached' })
        });
        closeUsageModal();
        await fetchTokenHealth();
        await fetchAgentQueue();
      } catch (e) {
        console.error('Error simulating token exhaustion:', e);
      }
    }

    async function clearSimulatedTokenExhaustion() {
      try {
        await fetch('/api/antigravity/tokens/simulate', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ status: 'clear' })
        });
        await fetchTokenHealth();
        await fetchAgentQueue();
      } catch (e) {
        console.error('Error clearing token simulation:', e);
      }
    }

    // --- Release Notes & Version History Modal ---

    async function fetchTokenHealth() {
      try {
        const res = await fetch('/api/antigravity/tokens');
        const data = await res.json();
        
        // Update header gauge
        const fill = document.getElementById('agTokenFill');
        const countLabel = document.getElementById('agTokenCountLabel');
        const banner = document.getElementById('agTokenExhaustedBanner');
        const bannerVaultBadge = document.getElementById('agTokenBannerVaultBadge');
        const fallbackName = document.getElementById('agFallbackModelName');
        const bannerTitle = document.getElementById('agTokenBannerTitle');
        const bannerDesc = document.getElementById('agTokenBannerDesc');
        
        const pct = data.percent_used || 0;
        if (countLabel) countLabel.innerText = `${pct}%`;
        if (fill) {
          fill.style.width = `${Math.min(100, Math.max(2, pct))}%`;
          if (data.status === 'exhausted') {
            fill.style.background = '#ef4444';
          } else if (data.status === 'warning') {
            fill.style.background = '#f59e0b';
          } else {
            fill.style.background = 'var(--accent-cyan)';
          }
        }
        
        // Show banner if exhausted or prompts are vaulted
        if (banner) {
          if (data.status === 'exhausted' || (data.vaulted_count && data.vaulted_count > 0)) {
            banner.style.display = 'block';
            banner.style.background = 'rgba(239, 68, 68, 0.15)';
            banner.style.borderColor = 'rgba(239, 68, 68, 0.4)';
            if (bannerTitle) bannerTitle.innerText = 'Token Limit Reached — Prompts Preserved';
            if (bannerDesc) bannerDesc.innerText = `Active model (${data.active_model_name || data.active_model_id}) context exhausted. All pending prompts are safely preserved in SQLite.`;
            if (bannerVaultBadge) bannerVaultBadge.innerText = `${data.vaulted_count || 0} Vaulted`;
            if (fallbackName) fallbackName.innerText = data.recommended_fallback_name || data.recommended_fallback || 'Gemini 3.8 Flash';
          } else if (data.status === 'warning') {
            banner.style.display = 'block';
            banner.style.background = 'rgba(245, 158, 11, 0.15)';
            banner.style.borderColor = 'rgba(245, 158, 11, 0.4)';
            if (bannerTitle) bannerTitle.innerText = 'Token Usage Warning (90%+)';
            if (bannerDesc) bannerDesc.innerText = 'Context window approaching limit. Subsequent prompts will automatically vault if exhaustion occurs.';
            if (bannerVaultBadge) bannerVaultBadge.innerText = 'Auto-Vault Ready';
            if (fallbackName) fallbackName.innerText = data.recommended_fallback_name || 'Gemini 3.8 Flash';
          } else {
            banner.style.display = 'none';
          }
        }
      } catch (e) {
        console.error('Error fetching token health:', e);
      }
    }

    // --- Message Queue & Parallel Agent Fleet State ---
    async function fetchAgentQueue() {
      try {
        const res = await fetch('/api/antigravity/queue');
        const data = await res.json();
        
        const activeCount = data.active_agents_count || 0;
        const maxSlots = data.max_parallel_agents || 4;
        const activeAgents = data.parallel_agents || [];

        // Parallel Capacity Meter & Slots
        const capacityBadge = document.getElementById('agParallelCapacityBadge');
        if (capacityBadge) {
          capacityBadge.innerText = `${activeCount} / ${maxSlots} Active Slots`;
          if (activeCount >= maxSlots) {
            capacityBadge.style.background = 'rgba(239, 68, 68, 0.2)';
            capacityBadge.style.color = '#f87171';
            capacityBadge.style.borderColor = 'rgba(239, 68, 68, 0.4)';
          } else if (activeCount > 0) {
            capacityBadge.style.background = 'rgba(0, 242, 254, 0.15)';
            capacityBadge.style.color = 'var(--accent-cyan)';
            capacityBadge.style.borderColor = 'rgba(0, 242, 254, 0.35)';
          } else {
            capacityBadge.style.background = 'rgba(16, 185, 129, 0.15)';
            capacityBadge.style.color = 'var(--accent-green)';
            capacityBadge.style.borderColor = 'rgba(16, 185, 129, 0.3)';
          }
        }

        const slotsRow = document.getElementById('agActiveSlotsRow');
        if (slotsRow) {
          if (activeAgents.length === 0) {
            slotsRow.innerHTML = `<span style="font-size: 11px; color: var(--text-muted); font-style: italic;">All slots ready</span>`;
          } else {
            slotsRow.innerHTML = activeAgents.map(a => `
              <span class="ag-pill-badge cyan" style="font-size: 10.5px; display: inline-flex; align-items: center; gap: 5px; padding: 2px 7px;" title="${escapeHtml(a.task || '')}">
                <span style="display:inline-block; width:6px; height:6px; border-radius:50%; background:#10b981;"></span>
                <strong>${escapeHtml(a.agent_id)}:</strong> ${escapeHtml((a.task || '').substring(0, 22))}...
              </span>
            `).join('');
          }
        }

        const concurrencySelect = document.getElementById('agConcurrencySelect');
        if (concurrencySelect && concurrencySelect.value !== String(maxSlots)) {
          concurrencySelect.value = String(maxSlots);
        }

        const stateBadge = document.getElementById('agAgentStateBadge');
        const sendBtn = document.getElementById('agSendBtn');
        if (data.status === 'paused_token_limit') {
          if (stateBadge) {
            stateBadge.innerText = '⚠️ Token Limit (Paused)';
            stateBadge.style.background = 'rgba(239, 68, 68, 0.2)';
            stateBadge.style.color = '#f87171';
            stateBadge.style.borderColor = 'rgba(239, 68, 68, 0.4)';
          }
          if (sendBtn) {
            sendBtn.innerHTML = '📦 Vault Prompt';
            sendBtn.style.background = 'linear-gradient(135deg, #ef4444, #b91c1c)';
          }
        } else if (activeCount >= maxSlots) {
          if (stateBadge) {
            stateBadge.innerText = `⚡ Parallel Slots Full (${activeCount}/${maxSlots})`;
            stateBadge.style.background = 'rgba(245, 158, 11, 0.18)';
            stateBadge.style.color = '#fbbf24';
            stateBadge.style.borderColor = 'rgba(245, 158, 11, 0.35)';
          }
          if (sendBtn) {
            sendBtn.innerHTML = '📥 Queue for Slot';
            sendBtn.style.background = 'linear-gradient(135deg, #f59e0b, #d97706)';
          }
        } else if (activeCount > 0) {
          if (stateBadge) {
            stateBadge.innerText = `🚀 ${activeCount}/${maxSlots} Parallel Agents`;
            stateBadge.style.background = 'rgba(0, 242, 254, 0.15)';
            stateBadge.style.color = 'var(--accent-cyan)';
            stateBadge.style.borderColor = 'rgba(0, 242, 254, 0.35)';
          }
          if (sendBtn) {
            sendBtn.innerHTML = '🚀 Launch Parallel Agent';
            sendBtn.style.background = 'linear-gradient(135deg, var(--accent-cyan), var(--accent-blue))';
          }
        } else {
          if (stateBadge) {
            stateBadge.innerText = `● ${maxSlots} Parallel Slots Ready`;
            stateBadge.style.background = 'rgba(16, 185, 129, 0.15)';
            stateBadge.style.color = 'var(--accent-green)';
            stateBadge.style.borderColor = 'rgba(16, 185, 129, 0.3)';
          }
          if (sendBtn) {
            sendBtn.innerHTML = '🚀 Launch Parallel Agent';
            sendBtn.style.background = 'linear-gradient(135deg, var(--accent-cyan), var(--accent-blue))';
          }
        }

        const banner = document.getElementById('agQueueBanner');
        const list = document.getElementById('agQueueList');
        const countBadge = document.getElementById('agQueueCountBadge');
        const fastTrackBtn = document.getElementById('agFastTrackBtn');
        const qItems = data.queue || [];

        if (fastTrackBtn) {
          fastTrackBtn.style.display = qItems.length > 0 ? 'inline-block' : 'none';
          fastTrackBtn.innerText = `🚀 Fast-Track ${qItems.length} Queued`;
        }

        if (qItems.length > 0) {
          if (banner) banner.style.display = 'block';
          if (countBadge) countBadge.innerText = qItems.length;
          if (list) {
            list.innerHTML = qItems.map(item => `
              <div class="ag-queue-item">
                <div style="display:flex; align-items:center; gap:8px; overflow:hidden;">
                  <span class="ag-pill-badge purple" style="font-size:10px;">#${item.id}</span>
                  <span style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:380px;">${escapeHtml(item.prompt || '(Image Attachment)')}</span>
                  <span class="ag-pill-badge gray" style="font-size:10px;">${escapeHtml(item.model || 'Default')}</span>
                </div>
                <button class="ag-queue-cancel" onclick="cancelQueueItem(${item.id})">✕ Cancel</button>
              </div>
            `).join('');
          }
        } else {
          if (banner) banner.style.display = 'none';
        }

        // Always sync token health alongside queue
        fetchTokenHealth();
      } catch (e) {
        console.error('Error fetching agent queue:', e);
      }
    }

    async function fastTrackAgentQueue() {
      try {
        const res = await fetch('/api/antigravity/fast_track', { method: 'POST', headers: {'Content-Type': 'application/json'} });
        const d = await res.json();
        await fetchAgentQueue();
      } catch (e) {
        console.error('Error fast-tracking queue:', e);
      }
    }

    async function changeConcurrencyLimit(val) {
      try {
        await fetch('/api/antigravity/parallel_limit', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ limit: parseInt(val, 10) })
        });
        await fetchAgentQueue();
      } catch (e) {
        console.error('Error changing concurrency limit:', e);
      }
    }

    async function cancelQueueItem(id) {
      try {
        await fetch('/api/antigravity/queue/cancel', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ id })
        });
        fetchAgentQueue();
      } catch (e) {
        console.error('Error cancelling queue item:', e);
      }
    }

    window.agChatEngineMode = 'antigravity_live'; // 'antigravity_live' | 'fleet_zero_token'

    function setAgChatEngineMode(mode) {
      window.agChatEngineMode = (mode === 'fleet_zero_token') ? 'fleet_zero_token' : 'antigravity_live';
      const isFleetZero = window.agChatEngineMode === 'fleet_zero_token';

      const btnLive = document.getElementById('btnAgModeLive');
      const btnFleet = document.getElementById('btnAgModeFleet');
      const liveScroll = document.getElementById('agChatScroll');
      const fleetScroll = document.getElementById('agFleetZeroChatScroll');
      const liveChips = document.getElementById('agLiveQuickChips');
      const fleetChips = document.getElementById('agFleetZeroQuickChips');
      const modelDropWrap = document.getElementById('agModelDropdownBtn');
      const input = document.getElementById('agCommandInput');
      const sendBtn = document.getElementById('agSendBtn');
      const costBadge = document.getElementById('agCostModeBadge');
      const footerLabel = document.getElementById('agConsoleFooterModeLabel');
      const parallelStrip = document.getElementById('agParallelFleetStrip');

      if (btnLive) {
        btnLive.style.background = !isFleetZero ? 'rgba(56, 189, 248, 0.2)' : 'rgba(255, 255, 255, 0.04)';
        btnLive.style.borderColor = !isFleetZero ? 'var(--accent-cyan)' : 'var(--card-border)';
        btnLive.style.color = !isFleetZero ? '#fff' : 'var(--text-muted)';
      }
      if (btnFleet) {
        btnFleet.style.background = isFleetZero ? 'rgba(16, 185, 129, 0.2)' : 'rgba(255, 255, 255, 0.04)';
        btnFleet.style.borderColor = isFleetZero ? 'var(--accent-green)' : 'var(--card-border)';
        btnFleet.style.color = isFleetZero ? '#fff' : 'var(--text-muted)';
      }

      if (liveScroll) liveScroll.style.display = isFleetZero ? 'none' : 'flex';
      if (fleetScroll) fleetScroll.style.display = isFleetZero ? 'flex' : 'none';
      if (liveChips) liveChips.style.display = isFleetZero ? 'none' : 'flex';
      if (fleetChips) fleetChips.style.display = isFleetZero ? 'flex' : 'none';
      if (modelDropWrap) modelDropWrap.style.display = isFleetZero ? 'none' : 'inline-flex';
      if (parallelStrip) {
        parallelStrip.style.display = isFleetZero ? 'none' : 'flex';
      }
      if (costBadge) {
        costBadge.innerText = isFleetZero ? '⚡ $0.00 Zero-Token Fleet Chat' : 'Tier 0 • 0 Tokens ($0.00)';
      }
      if (footerLabel) {
        footerLabel.innerText = isFleetZero ? '⚡ Instant $0.00 Local Fleet Conversational Engine' : '● Multi-Hyperscaler & Dev Tools Hub';
      }
      if (input) {
        input.placeholder = isFleetZero
          ? "Chat with Fleet at $0.00 ('hi', 'daily briefing', 'what is my workout?', '@discover')..."
          : "Ask Antigravity, paste image (Ctrl+V), /task, /sync, or type prompt...";
        input.focus();
      }
      if (sendBtn) {
        if (isFleetZero) {
          sendBtn.innerHTML = '⚡ Ask Fleet ($0.00)';
          sendBtn.style.background = 'linear-gradient(135deg, #10b981, #059669)';
        } else {
          fetchAgentQueue();
        }
      }
      if (isFleetZero) {
        renderAgFleetZeroChat();
      } else {
        fetchTranscript(true);
      }
    }

    function renderAgFleetZeroChat() {
      const container = document.getElementById('agFleetZeroChatScroll');
      if (!container) return;
      const turns = (typeof FleetNavigator !== 'undefined' && Array.isArray(FleetNavigator.omnibarChatTurns))
        ? FleetNavigator.omnibarChatTurns
        : [];

      if (turns.length === 0) {
        container.innerHTML = `
          <div style="margin: auto; max-width: 520px; text-align: center; padding: 28px 20px; background: rgba(15, 23, 42, 0.55); border: 1px solid var(--card-border); border-radius: 12px;">
            <div style="font-size: 28px; margin-bottom: 8px;">⚡🤖</div>
            <div style="font-size: 15px; font-weight: 700; color: var(--text); margin-bottom: 6px;">Zero-Token Conversational Fleet Assistant ($0.00)</div>
            <div style="font-size: 12.5px; color: var(--text-muted); line-height: 1.5; margin-bottom: 14px;">
              Chat naturally with your Personal Agentic Fleet at <strong>$0.00 token spend</strong>—ask about your daily briefing, pending tasks, hydration, 6-day Mudgal/Samtola/Bhim Gadha workouts, 35-page FFD diet &amp; smoothie rules, or agent creation. Switch to <strong>Antigravity Live</strong> anytime with 1 click!
            </div>
            <div style="display: flex; gap: 6px; flex-wrap: wrap; justify-content: center;">
              <button type="button" class="badge" style="cursor: pointer; padding: 5px 10px; background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.35);" onclick="sendZeroTokenFleetChatFromAg('hi')">👋 Say Hi</button>
              <button type="button" class="badge" style="cursor: pointer; padding: 5px 10px; background: rgba(56, 189, 248, 0.15); color: var(--accent-cyan); border: 1px solid rgba(56, 189, 248, 0.35);" onclick="sendZeroTokenFleetChatFromAg('Give me my daily briefing')">☀️ Daily Briefing</button>
              <button type="button" class="badge" style="cursor: pointer; padding: 5px 10px; background: rgba(56, 189, 248, 0.15); color: var(--accent-cyan); border: 1px solid rgba(56, 189, 248, 0.35);" onclick="sendZeroTokenFleetChatFromAg('What are my pending tasks?')">📋 Pending Tasks</button>
              <button type="button" class="badge" style="cursor: pointer; padding: 5px 10px; background: rgba(168, 85, 247, 0.15); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.35);" onclick="sendZeroTokenFleetChatFromAg('What is my workout today?')">🏋️ Workout Today</button>
              <button type="button" class="badge" style="cursor: pointer; padding: 5px 10px; background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.35);" onclick="sendZeroTokenFleetChatFromAg('FFD Green Smoothie recipe')">🥤 Smoothie Recipe</button>
              <button type="button" class="badge" style="cursor: pointer; padding: 5px 10px; background: rgba(56, 189, 248, 0.15); color: var(--accent-cyan); border: 1px solid rgba(56, 189, 248, 0.35);" onclick="sendZeroTokenFleetChatFromAg('@discover')">🕵️ @discover Agents</button>
            </div>
          </div>
        `;
        return;
      }

      const html = turns.map((turn, idx) => {
        const data = turn.data || {};
        const isLatest = idx === turns.length - 1;
        const suggestions = Array.isArray(data.suggestions) ? data.suggestions : [];
        const safePromptAttr = String(turn.userQuery || '').replace(/'/g, "\\'");

        const suggestionsHtml = (isLatest && suggestions.length > 0) ? `
          <div style="display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; padding-top: 8px; border-top: 1px solid rgba(255, 255, 255, 0.08);">
            ${suggestions.map(s => {
              const safeS = String(s).replace(/'/g, "\\'");
              return `<button type="button" class="badge" style="cursor: pointer; background: rgba(56, 189, 248, 0.14); color: var(--accent-cyan); border: 1px solid rgba(56, 189, 248, 0.3); font-size: 11px; padding: 3px 8px;" onclick="sendZeroTokenFleetChatFromAg('${safeS}')">💬 ${escapeHtml(s)}</button>`;
            }).join('')}
          </div>
        ` : '';

        return `
          <div class="ag-message ag-msg-user">
            <div class="ag-msg-role">👤 You</div>
            <div>${formatMarkdown(turn.userQuery || '')}</div>
          </div>
          <div class="ag-message ag-msg-assistant" style="border-left: 3px solid var(--accent-green);">
            <div class="ag-msg-role" style="display: flex; justify-content: space-between; align-items: center; gap: 8px;">
              <span>${escapeHtml(data.title || '⚡ Fleet Conversational Assistant ($0.00)')}</span>
              <div style="display: flex; gap: 6px; align-items: center;">
                ${data.agent_id ? `<button type="button" class="btn btn-sm" style="font-size: 10.5px; padding: 2px 7px;" onclick="FleetNavigator.switchAgent('${escapeHtml(data.agent_id)}')">Open ${escapeHtml(data.agent_id)} →</button>` : ''}
                <button type="button" class="btn btn-sm" style="font-size: 10.5px; padding: 2px 7px; border-color: rgba(56, 189, 248, 0.35); color: var(--accent-cyan);" onclick="escalateZeroTokenTurnToAgLive('${safePromptAttr}')" title="Send this prompt to Antigravity 2.0 Live LLM">🚀 Send to Antigravity Live</button>
              </div>
            </div>
            <div>${formatMarkdown(data.message || '')}</div>
            ${suggestionsHtml}
          </div>
        `;
      }).join('');

      container.innerHTML = html;
      container.scrollTop = container.scrollHeight;
    }

    async function sendZeroTokenFleetChatFromAg(queryText) {
      const q = (queryText || '').trim();
      if (!q) return;
      if (window.agChatEngineMode !== 'fleet_zero_token') {
        setAgChatEngineMode('fleet_zero_token');
      }
      if (typeof FleetNavigator !== 'undefined' && typeof FleetNavigator.executeOmnibarInput === 'function') {
        await FleetNavigator.executeOmnibarInput(q);
      }
      const input = document.getElementById('agCommandInput');
      if (input) {
        input.value = '';
        input.focus();
      }
      renderAgFleetZeroChat();
    }

    function escalateZeroTokenTurnToAgLive(promptText) {
      setAgChatEngineMode('antigravity_live');
      const input = document.getElementById('agCommandInput');
      if (input) {
        input.value = promptText || '';
        input.focus();
      }
    }

    function openAntigravityRightDock() {
      const viewAg = document.getElementById('viewAntigravity');
      const dockSlot = document.getElementById('agRightDockSlot');
      const btnToggle = document.getElementById('btnToggleAgRightDock');
      const btnClose = document.getElementById('btnCloseAgRightDock');
      const btnHeader = document.getElementById('btnHeaderRightDockChat');
      const btnGlobalHeader = document.getElementById('btnGlobalHeaderRightDock');

      if (!viewAg || !dockSlot) return;
      window.isAgRightDocked = true;
      try {
        localStorage.setItem('fleet_ag_right_docked', '1');
      } catch (e) {}

      if (viewAg.parentElement !== dockSlot) {
        dockSlot.appendChild(viewAg);
      }
      dockSlot.style.display = 'flex';
      viewAg.style.display = 'flex';
      viewAg.classList.add('ag-docked-right');

      if (btnToggle) {
        btnToggle.innerHTML = '⤢ Full Page';
        btnToggle.title = 'Expand chatbot to full page tab';
      }
      if (btnClose) btnClose.style.display = 'inline-flex';
      if (btnHeader) {
        btnHeader.innerHTML = '◨ Hide Chat Panel';
        btnHeader.style.background = 'rgba(0, 242, 254, 0.2)';
        btnHeader.style.color = 'var(--accent-cyan)';
      }
      if (btnGlobalHeader) {
        btnGlobalHeader.innerHTML = '◨ Hide Right Chat';
        btnGlobalHeader.style.background = 'rgba(16, 185, 129, 0.18)';
        btnGlobalHeader.style.borderColor = 'rgba(16, 185, 129, 0.45)';
        btnGlobalHeader.style.color = 'var(--accent-green)';
      }

      fetchTranscript(true);
      fetchModels();
      fetchAgentQueue();
      if (!agInterval) {
        agInterval = setInterval(() => {
          fetchTranscript(false);
          fetchAgentQueue();
        }, 2500);
      }

      // If user was on the full-page antigravity tab, restore the left main stage to their previous agent tab
      if (typeof currentTab !== 'undefined' && currentTab === 'antigravity') {
        const targetTab = (window.lastNonAgTab && window.lastNonAgTab !== 'antigravity') ? window.lastNonAgTab : 'health';
        if (typeof FleetNavigator !== 'undefined' && typeof FleetNavigator.switchAgent === 'function') {
          FleetNavigator.switchAgent(targetTab);
        } else if (typeof switchTab === 'function') {
          switchTab(targetTab);
        }
      }
    }

    function closeAntigravityRightDock() {
      const viewAg = document.getElementById('viewAntigravity');
      const dockSlot = document.getElementById('agRightDockSlot');
      const mainAnchor = document.getElementById('agMainStageAnchor');
      const btnToggle = document.getElementById('btnToggleAgRightDock');
      const btnClose = document.getElementById('btnCloseAgRightDock');
      const btnHeader = document.getElementById('btnHeaderRightDockChat');
      const btnGlobalHeader = document.getElementById('btnGlobalHeaderRightDock');

      window.isAgRightDocked = false;
      try {
        localStorage.setItem('fleet_ag_right_docked', '0');
      } catch (e) {}

      if (viewAg && mainAnchor && mainAnchor.parentNode) {
        mainAnchor.parentNode.insertBefore(viewAg, mainAnchor.nextSibling);
        viewAg.classList.remove('ag-docked-right');
        if (typeof currentTab !== 'undefined' && currentTab !== 'antigravity') {
          viewAg.style.display = 'none';
        }
      }
      if (dockSlot) dockSlot.style.display = 'none';
      if (btnToggle) {
        btnToggle.innerHTML = '◨ Dock to Right Panel';
        btnToggle.title = 'Dock chatbot to the right panel so you can browse other agent pages while chatting';
      }
      if (btnClose) btnClose.style.display = 'none';
      if (btnHeader) {
        btnHeader.innerHTML = '◨ Show Chat Panel';
        btnHeader.style.background = 'rgba(16, 185, 129, 0.12)';
        btnHeader.style.color = 'var(--accent-green)';
      }
      if (btnGlobalHeader) {
        btnGlobalHeader.innerHTML = '◨ Show Right Chat';
        btnGlobalHeader.style.background = 'rgba(0, 242, 254, 0.08)';
        btnGlobalHeader.style.borderColor = 'rgba(0, 242, 254, 0.35)';
        btnGlobalHeader.style.color = 'var(--accent-cyan)';
      }
    }

    function toggleAntigravityRightDock(forceState) {
      const nextState = (typeof forceState === 'boolean') ? forceState : !window.isAgRightDocked;
      if (nextState) {
        openAntigravityRightDock();
      } else {
        closeAntigravityRightDock();
      }
    }

    function toggleAntigravityFullPageOrDock() {
      if (window.isAgRightDocked) {
        closeAntigravityRightDock();
        if (typeof switchTab === 'function') {
          switchTab('antigravity');
        }
      } else {
        openAntigravityRightDock();
      }
    }

    function dockFleetChatToRightPanel() {
      openAntigravityRightDock();
      setAgChatEngineMode('fleet_zero_token');
    }

    async function submitAgCommand() {
      const input = document.getElementById('agCommandInput');
      const cmd = input.value.trim();
      const images = attachedImages.map(img => img.path || img.filename);
      if (!cmd && images.length === 0) return;

      // If in Zero-Token Fleet Chat mode (and no image attachments), route directly to $0.00 Conversational Fleet Assistant
      if (window.agChatEngineMode === 'fleet_zero_token' && images.length === 0) {
        await sendZeroTokenFleetChatFromAg(cmd);
        return;
      }

      const toast = document.getElementById('cmdToast');
      toast.style.display = 'block';
      toast.className = 'cmd-toast';
      toast.innerText = '⚡ Processing command...';

      try {
        const res = await fetch('/api/antigravity/command', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            command: cmd,
            images: images,
            model: activeModelId
          })
        });
        const result = await res.json();
        if (result.status === 'success' || result.status === 'queued') {
          toast.className = 'cmd-toast success';
          toast.innerText = `✅ ${result.message}`;
          input.value = '';
          if (input.style) input.style.height = '';
          attachedImages = [];
          renderAttachmentStrip();
          fetchTranscript(true);
          fetchAgentQueue();
          fetchTasks();
          fetchBriefing();
          fetchLogs();
          fetchEmails();
        } else if (result.status === 'vaulted') {
          toast.className = 'cmd-toast';
          toast.style.background = 'rgba(239, 68, 68, 0.95)';
          toast.innerText = `📦 ${result.message}`;
          input.value = '';
          if (input.style) input.style.height = '';
          attachedImages = [];
          renderAttachmentStrip();
          fetchTokenHealth();
          fetchAgentQueue();
        } else {
          toast.className = 'cmd-toast error';
          toast.innerText = `❌ ${result.message}`;
        }
      } catch (e) {
        toast.className = 'cmd-toast error';
        toast.innerText = `Error: ${e.message}`;
      }

      setTimeout(() => {
        if (toast) toast.style.display = 'none';
      }, 5000);
    }


window.fetchTranscript = fetchTranscript;
window.fillCommand = fillCommand;
window.uploadImageBlob = uploadImageBlob;
window.handleImageFileSelect = handleImageFileSelect;
window.renderAttachmentStrip = renderAttachmentStrip;
window.removeAttachment = removeAttachment;
window.openImageLightbox = openImageLightbox;
window.closeImageLightbox = closeImageLightbox;
window.fetchModels = fetchModels;
window.toggleModelMenu = toggleModelMenu;
window.selectModel = selectModel;
window.openUsageModal = openUsageModal;
window.closeUsageModal = closeUsageModal;
window.openVaultModal = openVaultModal;
window.closeVaultModal = closeVaultModal;
window.resumeVaultedWork = resumeVaultedWork;
window.simulateTokenExhaustion = simulateTokenExhaustion;
window.clearSimulatedTokenExhaustion = clearSimulatedTokenExhaustion;
window.fetchTokenHealth = fetchTokenHealth;
window.fetchAgentQueue = fetchAgentQueue;
window.fastTrackAgentQueue = fastTrackAgentQueue;
window.changeConcurrencyLimit = changeConcurrencyLimit;
window.cancelQueueItem = cancelQueueItem;
window.submitAgCommand = submitAgCommand;
window.setAgChatEngineMode = setAgChatEngineMode;
window.renderAgFleetZeroChat = renderAgFleetZeroChat;
window.sendZeroTokenFleetChatFromAg = sendZeroTokenFleetChatFromAg;
window.escalateZeroTokenTurnToAgLive = escalateZeroTokenTurnToAgLive;
window.openAntigravityRightDock = openAntigravityRightDock;
window.toggleAntigravityRightDock = toggleAntigravityRightDock;
window.toggleAntigravityFullPageOrDock = toggleAntigravityFullPageOrDock;
window.closeAntigravityRightDock = closeAntigravityRightDock;
window.dockFleetChatToRightPanel = dockFleetChatToRightPanel;

// --- J.A.R.V.I.S. Bi-Directional Audio Conversation, Biometric Speaker Lock & Live Activity Engine ---
let _initialVoiceprint = null;
try {
  const rawVp = localStorage.getItem('afcc_jarvis_voiceprint');
  if (rawVp) _initialVoiceprint = JSON.parse(rawVp);
} catch (e) {}

window.AFCCVoice = {
  isListening: false,
  userWantsListening: false,
  isSpeaking: false,
  continuousMode: localStorage.getItem('afcc_voice_continuous') !== 'false',
  spokenReplyEnabled: localStorage.getItem('afcc_voice_tts_enabled') !== 'false',
  speechRate: parseFloat(localStorage.getItem('afcc_voice_rate') || '1.05') || 1.05,
  voiceLanguage: localStorage.getItem('afcc_voice_lang') || 'en',
  voiceGender: localStorage.getItem('afcc_voice_gender') || 'female',
  voiceAccent: localStorage.getItem('afcc_voice_accent') || 'IN',
  routingMode: localStorage.getItem('afcc_voice_routing_mode') || 'zero_token',
  speakerLockEnabled: localStorage.getItem('afcc_voice_speaker_lock') !== 'false',
  wakeWordRequired: localStorage.getItem('afcc_voice_wake_word_lock') === 'true',
  voiceprint: _initialVoiceprint,
  isCalibrating: false,
  audioCtx: null,
  mediaStream: null,
  analyser: null,
  dspTimer: null,
  liveSnrDb: 0,
  livePitchHz: 0,
  liveCentroidHz: 0,
  utterancePitchSamples: [],
  utteranceCentroidSamples: [],
  utterancePeakSnrDb: 0,
  lastSpokenReply: 'Loud and clear! I am J.A.R.V.I.S., your Personal Agentic Fleet Voice Copilot. Tell me what you would like to do.',
  lastSpokenPhonetic: 'Loud and clear! I am Jarvis, your Personal Agentic Fleet Voice Copilot. Tell me what you would like to do.',
  recognition: null
};

async function loadJarvisVoiceprintFromServer() {
  try {
    const res = await fetch('/api/voice/voiceprint');
    if (!res.ok) return;
    const data = await res.json();
    if (data && data.enrolled && data.profile && data.profile.pitchMeanHz) {
      window.AFCCVoice.voiceprint = data.profile;
      try {
        localStorage.setItem('afcc_jarvis_voiceprint', JSON.stringify(data.profile));
      } catch (e) {}
      syncVoiceProfileSelectors();
    }
  } catch (e) {}
}
setTimeout(loadJarvisVoiceprintFromServer, 800);

function setAfccVoiceRoutingMode(mode) {
  const clean = String(mode || 'zero_token').toLowerCase() === 'antigravity' ? 'antigravity' : 'zero_token';
  window.AFCCVoice.routingMode = clean;
  try {
    localStorage.setItem('afcc_voice_routing_mode', clean);
  } catch (e) {}
  syncVoiceProfileSelectors();
}

function toggleVoiceSpeakerLock() {
  window.AFCCVoice.speakerLockEnabled = !window.AFCCVoice.speakerLockEnabled;
  try {
    localStorage.setItem('afcc_voice_speaker_lock', window.AFCCVoice.speakerLockEnabled ? 'true' : 'false');
  } catch (e) {}
  syncVoiceProfileSelectors();
}

function toggleVoiceWakeWordLock() {
  window.AFCCVoice.wakeWordRequired = !window.AFCCVoice.wakeWordRequired;
  try {
    localStorage.setItem('afcc_voice_wake_word_lock', window.AFCCVoice.wakeWordRequired ? 'true' : 'false');
  } catch (e) {}
  syncVoiceProfileSelectors();
}

function computeAutocorrelationPitchHz(floatBuf, sampleRate) {
  const size = floatBuf.length;
  let rms = 0;
  for (let i = 0; i < size; i++) {
    rms += floatBuf[i] * floatBuf[i];
  }
  rms = Math.sqrt(rms / size);
  if (rms < 0.012) return 0; // Silence or faint background

  // Human fundamental vocal pitch F0 range: 75 Hz to 360 Hz
  const minLag = Math.floor(sampleRate / 360);
  const maxLag = Math.min(Math.floor(sampleRate / 75), Math.floor(size / 2));
  let bestLag = -1;
  let bestCorr = 0;

  for (let lag = minLag; lag <= maxLag; lag++) {
    let sum = 0;
    for (let i = 0; i < maxLag; i++) {
      sum += floatBuf[i] * floatBuf[i + lag];
    }
    if (sum > bestCorr) {
      bestCorr = sum;
      bestLag = lag;
    }
  }
  if (bestLag <= 0) return 0;
  const f0 = sampleRate / bestLag;
  return (f0 >= 75 && f0 <= 360) ? Math.round(f0) : 0;
}

function computeSpectralCentroidHz(freqByteBuf, sampleRate, fftSize) {
  let weightedSum = 0;
  let magSum = 0;
  const binHz = sampleRate / fftSize;
  const maxBin = Math.min(freqByteBuf.length, Math.ceil(3800 / binHz));
  const minBin = Math.max(1, Math.floor(85 / binHz));
  for (let i = minBin; i < maxBin; i++) {
    const mag = freqByteBuf[i];
    if (mag > 12) {
      weightedSum += (i * binHz) * mag;
      magSum += mag;
    }
  }
  return magSum > 0 ? Math.round(weightedSum / magSum) : 0;
}

async function ensureJarvisAudioDspPipeline() {
  if (window.AFCCVoice.audioCtx && window.AFCCVoice.analyser && window.AFCCVoice.mediaStream) {
    if (window.AFCCVoice.audioCtx.state === 'suspended') {
      try { await window.AFCCVoice.audioCtx.resume(); } catch (e) {}
    }
    return true;
  }
  if (!navigator.mediaDevices || typeof navigator.mediaDevices.getUserMedia !== 'function') {
    return false;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        channelCount: 1
      }
    });
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return true;

    const ctx = new AudioCtx();
    const source = ctx.createMediaStreamSource(stream);

    // 1. High-Pass Filter @ 85 Hz (strips fan rumble, AC hum, and desk thumps)
    const highPass = ctx.createBiquadFilter();
    highPass.type = 'highpass';
    highPass.frequency.value = 85;
    highPass.Q.value = 0.707;

    // 2. Low-Pass Filter @ 3800 Hz (isolates human speech formants & blocks high-freq hiss)
    const lowPass = ctx.createBiquadFilter();
    lowPass.type = 'lowpass';
    lowPass.frequency.value = 3800;
    lowPass.Q.value = 0.707;

    // 3. Biometric & SNR AnalyserNode
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 2048;
    analyser.smoothingTimeConstant = 0.6;

    source.connect(highPass);
    highPass.connect(lowPass);
    lowPass.connect(analyser);

    window.AFCCVoice.audioCtx = ctx;
    window.AFCCVoice.mediaStream = stream;
    window.AFCCVoice.analyser = analyser;

    if (window.AFCCVoice.dspTimer) clearInterval(window.AFCCVoice.dspTimer);
    const timeBuf = new Float32Array(analyser.fftSize);
    const freqBuf = new Uint8Array(analyser.frequencyBinCount);

    window.AFCCVoice.dspTimer = setInterval(() => {
      if (!window.AFCCVoice.analyser || (!window.AFCCVoice.isListening && !window.AFCCVoice.isCalibrating)) return;
      try {
        analyser.getFloatTimeDomainData(timeBuf);
        analyser.getByteFrequencyData(freqBuf);

        let sumSq = 0;
        for (let i = 0; i < timeBuf.length; i++) {
          sumSq += timeBuf[i] * timeBuf[i];
        }
        const rms = Math.sqrt(sumSq / timeBuf.length);
        const snrDb = Math.max(0, Math.round(20 * Math.log10((rms + 1e-6) / 0.002)));
        const pitchHz = computeAutocorrelationPitchHz(timeBuf, ctx.sampleRate || 48000);
        const centroidHz = computeSpectralCentroidHz(freqBuf, ctx.sampleRate || 48000, analyser.fftSize);

        window.AFCCVoice.liveSnrDb = snrDb;
        window.AFCCVoice.livePitchHz = pitchHz;
        window.AFCCVoice.liveCentroidHz = centroidHz;

        if (snrDb > window.AFCCVoice.utterancePeakSnrDb) {
          window.AFCCVoice.utterancePeakSnrDb = snrDb;
        }
        if (pitchHz >= 75 && pitchHz <= 360 && snrDb >= 10) {
          window.AFCCVoice.utterancePitchSamples.push(pitchHz);
          if (centroidHz > 0) window.AFCCVoice.utteranceCentroidSamples.push(centroidHz);
        }

        const dspBadge = document.getElementById('voiceDspStatusBadge');
        if (dspBadge) {
          dspBadge.textContent = pitchHz > 0
            ? `SNR ${snrDb}dB • F0 ${pitchHz}Hz`
            : `SNR ${snrDb}dB • 85-3800Hz`;
        }
      } catch (e) {}
    }, 110);

    return true;
  } catch (err) {
    return false;
  }
}

function stopJarvisAudioDspPipeline() {
  if (window.AFCCVoice.dspTimer) {
    clearInterval(window.AFCCVoice.dspTimer);
    window.AFCCVoice.dspTimer = null;
  }
  if (window.AFCCVoice.mediaStream && typeof window.AFCCVoice.mediaStream.getTracks === 'function') {
    window.AFCCVoice.mediaStream.getTracks().forEach(t => { try { t.stop(); } catch (e) {} });
  }
  if (window.AFCCVoice.audioCtx && typeof window.AFCCVoice.audioCtx.close === 'function') {
    try { window.AFCCVoice.audioCtx.close(); } catch (e) {}
  }
  window.AFCCVoice.audioCtx = null;
  window.AFCCVoice.mediaStream = null;
  window.AFCCVoice.analyser = null;
}

async function calibrateJarvisVoiceprint() {
  const transcriptEl = document.getElementById('voiceTranscriptText');
  const btnEnroll = document.getElementById('btnEnrollVoiceprint');
  window.AFCCVoice.isCalibrating = true;
  window.AFCCVoice.utterancePitchSamples = [];
  window.AFCCVoice.utteranceCentroidSamples = [];
  window.AFCCVoice.utterancePeakSnrDb = 0;

  if (btnEnroll) {
    btnEnroll.innerHTML = '🎙️ Speak Now (3s)...';
  }
  if (transcriptEl) {
    transcriptEl.innerHTML = `<span style="color: #38bdf8; font-weight: 600;">🧬 Calibrating Biometric Voiceprint: Please say "Jarvis, can you hear my voice clearly?" aloud now...</span>`;
  }

  const ok = await ensureJarvisAudioDspPipeline();
  if (!ok) {
    window.AFCCVoice.isCalibrating = false;
    if (btnEnroll) btnEnroll.innerHTML = '🧬 Calibrate My Voice (3s)';
    if (transcriptEl) {
      transcriptEl.innerHTML = `<span style="color: #fb7185;">Could not access microphone for voiceprint calibration. Check browser mic permissions.</span>`;
    }
    return;
  }

  setTimeout(async () => {
    window.AFCCVoice.isCalibrating = false;
    const pitches = window.AFCCVoice.utterancePitchSamples.slice();
    const centroids = window.AFCCVoice.utteranceCentroidSamples.slice();

    // Compute user's fundamental pitch mean & variance (fallback to natural vocal profile if user was quiet)
    let pitchMeanHz = 145;
    let pitchStdHz = 28;
    let centroidMeanHz = 1150;

    if (pitches.length >= 2) {
      const sum = pitches.reduce((a, b) => a + b, 0);
      pitchMeanHz = Math.round(sum / pitches.length);
      const variance = pitches.reduce((acc, v) => acc + Math.pow(v - pitchMeanHz, 2), 0) / pitches.length;
      pitchStdHz = Math.max(18, Math.round(Math.sqrt(variance)));
    } else if (window.AFCCVoice.voiceGender === 'female') {
      pitchMeanHz = 195;
    }

    if (centroids.length >= 2) {
      centroidMeanHz = Math.round(centroids.reduce((a, b) => a + b, 0) / centroids.length);
    }

    const profile = {
      pitchMeanHz,
      pitchStdHz,
      centroidMeanHz,
      snrFloorDb: Math.max(10, Math.min(22, (window.AFCCVoice.utterancePeakSnrDb || 18) - 8)),
      samplesCount: pitches.length,
      enrolledAt: new Date().toISOString()
    };

    window.AFCCVoice.voiceprint = profile;
    window.AFCCVoice.speakerLockEnabled = true;
    try {
      localStorage.setItem('afcc_jarvis_voiceprint', JSON.stringify(profile));
      localStorage.setItem('afcc_voice_speaker_lock', 'true');
    } catch (e) {}

    try {
      await fetch('/api/voice/voiceprint', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile })
      });
    } catch (e) {}

    syncVoiceProfileSelectors();
    const msg = `Biometric Voiceprint Locked! Your vocal pitch signature (${pitchMeanHz} Hz, Formant Centroid ${centroidMeanHz} Hz) is now enrolled. Background speakers and room noise will be filtered out automatically.`;
    if (transcriptEl) {
      transcriptEl.innerHTML = `<span style="color: #34d399; font-weight: 600;">🧬 ${escapeHtml(msg)}</span>`;
    }
    speakAfccVoiceText(msg);
  }, 3100);
}

function verifySpeakerBiometrics(transcript, alternatives) {
  const clean = String(transcript || '').trim();
  if (!clean) return { allowed: false, reason: 'Empty transcript' };

  const hasWakeWord = /\b(jarvis|afcc|hey\s+jarvis|ok\s+jarvis|hello\s+jarvis)\b/i.test(clean) ||
    (Array.isArray(alternatives) && alternatives.some(a => /\b(jarvis|afcc)\b/i.test(String(a || ''))));

  if (window.AFCCVoice.wakeWordRequired && !hasWakeWord) {
    return {
      allowed: false,
      reason: 'Wake Word Lock is ON — say "Jarvis ..." to issue a command.'
    };
  }

  if (!window.AFCCVoice.speakerLockEnabled) {
    return { allowed: true, matchPct: 100 };
  }

  const vp = window.AFCCVoice.voiceprint;
  const pitches = window.AFCCVoice.utterancePitchSamples || [];
  const peakSnr = window.AFCCVoice.utterancePeakSnrDb || 0;

  // If we have a calibrated voiceprint and measured pitch samples during this utterance, verify F0 proximity
  if (vp && vp.pitchMeanHz && pitches.length >= 3 && !hasWakeWord) {
    const uttMeanPitch = Math.round(pitches.reduce((a, b) => a + b, 0) / pitches.length);
    const diffHz = Math.abs(uttMeanPitch - vp.pitchMeanHz);
    const toleranceHz = Math.max(58, (vp.pitchStdHz || 25) * 2.4);
    const matchPct = Math.max(0, Math.min(99, Math.round(100 - (diffHz / 1.6))));

    const bioBadge = document.getElementById('voiceBiometricMatchBadge');
    if (bioBadge) {
      bioBadge.textContent = `Speaker Match: ${matchPct}% (${uttMeanPitch}Hz)`;
    }

    if (diffHz > toleranceHz) {
      return {
        allowed: false,
        matchPct,
        reason: `Background voice rejected (${uttMeanPitch}Hz vs your ${vp.pitchMeanHz}Hz voiceprint).`
      };
    }
    return { allowed: true, matchPct };
  }

  // Low-SNR single-word background chatter check
  const words = clean.split(/\s+/).filter(Boolean);
  if (words.length === 1 && peakSnr > 0 && peakSnr < 9 && !hasWakeWord) {
    return {
      allowed: false,
      reason: `Filtered faint background noise (${peakSnr} dB).`
    };
  }

  return { allowed: true, matchPct: vp ? 96 : 100 };
}

function selectBestJarvisClientAlternative(alternatives) {
  if (!Array.isArray(alternatives) || alternatives.length === 0) return '';
  const cleaned = alternatives.map(a => String(a || '').trim()).filter(Boolean);
  if (cleaned.length === 0) return '';
  if (cleaned.length === 1) return cleaned[0];

  const highValueRegex = /\b(can you hear|hear me|jarvis|are you there|mic check|audible|what agents|list agents|my agents|about .* agent|health agent|optimizer agent|email agent|backlog agent|overview agent|antigravity|daily briefing|water|workout|playlist|video|optimize|security scan|emails|tasks|smoothie|weight|fasting)\b/i;
  const noiseWords = new Set(['crisis', 'crying', 'christ', 'prices', 'places', 'the', 'a', 'uh', 'um', 'hmm']);

  let best = cleaned[0];
  let bestScore = -999;

  cleaned.forEach((cand, idx) => {
    let score = idx === 0 ? 10 : 0;
    const lower = cand.toLowerCase();
    if (highValueRegex.test(lower)) score += 100;
    if (noiseWords.has(lower)) score -= 80;
    if (cand.split(/\s+/).length >= 2) score += 15;
    if (score > bestScore) {
      bestScore = score;
      best = cand;
    }
  });
  return best;
}

function getTargetVoiceLocale() {
  const lang = String(window.AFCCVoice.voiceLanguage || 'en').toLowerCase();
  const acc = String(window.AFCCVoice.voiceAccent || 'IN').toUpperCase();
  if (lang === 'hi') return 'hi-IN';
  if (lang === 'te') return 'te-IN';
  if (lang === 'mr') return 'mr-IN';
  if (acc === 'US') return 'en-US';
  if (acc === 'GB') return 'en-GB';
  return 'en-IN';
}

function getVoiceProfileDisplayLabel() {
  const lang = String(window.AFCCVoice.voiceLanguage || 'en').toLowerCase();
  const gen = String(window.AFCCVoice.voiceGender || 'female').toLowerCase() === 'male' ? 'Male' : 'Lady';
  const acc = String(window.AFCCVoice.voiceAccent || 'IN').toUpperCase();
  const bcp47 = getTargetVoiceLocale();
  const langNames = { en: 'English', hi: 'Hindi', te: 'Telugu', mr: 'Marathi' };
  const accFlags = { IN: '🇮🇳 Indian', US: '🇺🇸 US', GB: '🇬🇧 UK' };
  const flagLabel = (lang === 'en') ? (accFlags[acc] || '🇮🇳 Indian') : '🇮🇳 Indian';
  return `${flagLabel} ${gen} • ${langNames[lang] || 'English'} (${bcp47})`;
}

function syncVoiceProfileSelectors() {
  const langSel = document.getElementById('voiceLanguageSelect');
  const genSel = document.getElementById('voiceGenderSelect');
  const accSel = document.getElementById('voiceAccentSelect');
  const rateSel = document.getElementById('voiceRateSelect');
  const profBadge = document.getElementById('voiceActiveProfileBadge');
  const routeSel = document.getElementById('voiceRoutingModeSelect');
  const btnSpeakerLock = document.getElementById('btnVoiceSpeakerLock');
  const btnEnroll = document.getElementById('btnEnrollVoiceprint');
  const btnWake = document.getElementById('btnVoiceWakeWordMode');
  const bioBadge = document.getElementById('voiceBiometricMatchBadge');

  if (langSel && langSel.value !== window.AFCCVoice.voiceLanguage) {
    langSel.value = window.AFCCVoice.voiceLanguage || 'en';
  }
  if (genSel && genSel.value !== window.AFCCVoice.voiceGender) {
    genSel.value = window.AFCCVoice.voiceGender || 'female';
  }
  if (accSel && accSel.value !== window.AFCCVoice.voiceAccent) {
    accSel.value = window.AFCCVoice.voiceAccent || 'IN';
  }
  if (rateSel && String(rateSel.value) !== String(window.AFCCVoice.speechRate)) {
    rateSel.value = String(window.AFCCVoice.speechRate || 1.05);
  }
  if (profBadge) {
    profBadge.textContent = getVoiceProfileDisplayLabel();
  }
  if (routeSel && routeSel.value !== window.AFCCVoice.routingMode) {
    routeSel.value = window.AFCCVoice.routingMode || 'zero_token';
  }
  if (btnSpeakerLock) {
    const sOn = Boolean(window.AFCCVoice.speakerLockEnabled);
    btnSpeakerLock.innerHTML = sOn ? '🛡️ My Voice Only: ON' : '🛡️ My Voice Only: OFF';
    btnSpeakerLock.style.color = sOn ? '#34d399' : 'var(--text-muted)';
    btnSpeakerLock.style.borderColor = sOn ? 'rgba(16, 185, 129, 0.45)' : 'var(--card-border)';
    btnSpeakerLock.style.background = sOn ? 'rgba(16, 185, 129, 0.14)' : 'rgba(255,255,255,0.04)';
  }
  if (btnEnroll && !window.AFCCVoice.isCalibrating) {
    const vp = window.AFCCVoice.voiceprint;
    if (vp && vp.pitchMeanHz) {
      btnEnroll.innerHTML = `🧬 Voiceprint (${vp.pitchMeanHz}Hz)`;
      btnEnroll.style.borderColor = 'rgba(16, 185, 129, 0.45)';
      btnEnroll.style.color = '#34d399';
    } else {
      btnEnroll.innerHTML = '🧬 Calibrate My Voice (3s)';
    }
  }
  if (btnWake) {
    const wOn = Boolean(window.AFCCVoice.wakeWordRequired);
    btnWake.innerHTML = wOn ? '🔒 Wake Word: "Jarvis"' : '🟢 Wake Word: Optional';
    btnWake.style.color = wOn ? '#fbbf24' : 'var(--text-muted)';
    btnWake.style.borderColor = wOn ? 'rgba(245, 158, 11, 0.45)' : 'var(--card-border)';
  }
  if (bioBadge && !window.AFCCVoice.isListening) {
    const vp = window.AFCCVoice.voiceprint;
    bioBadge.textContent = (vp && vp.pitchMeanHz)
      ? `Locked: ${vp.pitchMeanHz}Hz`
      : (window.AFCCVoice.speakerLockEnabled ? 'Noise Shield: Active' : 'Shield: Off');
  }
}

function resolveBestSpeechVoice(voices, langCode, gender, accent) {
  if (!Array.isArray(voices) || voices.length === 0) return null;
  const lang = String(langCode || 'en').toLowerCase();
  const gen = String(gender || 'female').toLowerCase() === 'male' ? 'male' : 'female';
  const acc = String(accent || 'IN').toUpperCase();

  const femaleNameRegex = /Female|Heera|Neerja|Swara|Shruti|Aarohi|Kalpana|Pallavi|Kavya|Ananya|Vani|Zira|Hazel|Aria|Jenny|Sonia|Libby|Natasha|Clara|Google हिन्दी|Google తెలుగు|Google मराठी|Google UK English Female|Google US English/i;
  const maleNameRegex = /\bMale\b|Ravi|Prabhat|Madhur|Mohan|Manohar|Hemant|Sagar|Valluvar|David|Guy|Ryan|George|Mark|Christopher|Eric|Google UK English Male/i;
  const indianFemaleRegex = /Heera|Neerja|Swara|Shruti|Aarohi|Kalpana|Pallavi|Kavya|Ananya|Vani|Google हिन्दी|Google తెలుగు|Google मराठी/i;
  const indianMaleRegex = /Ravi|Prabhat|Madhur|Mohan|Manohar|Hemant|Sagar|Valluvar/i;

  let bestVoice = null;
  let bestScore = -999;

  for (const v of voices) {
    const vName = String(v.name || '');
    const vLang = String(v.lang || '').replace('_', '-');
    let score = 0;

    const isFemaleVoice = femaleNameRegex.test(vName) && !maleNameRegex.test(vName);
    const isMaleVoice = maleNameRegex.test(vName);

    // 1. Gender preference scoring
    if (gen === 'female') {
      if (isFemaleVoice) score += 80;
      if (isMaleVoice) score -= 100;
    } else {
      if (isMaleVoice) score += 80;
      if (isFemaleVoice) score -= 100;
    }

    // 2. Language & Accent scoring
    if (lang === 'te') {
      if (/^te/i.test(vLang) || /Telugu|తెలుగు|Shruti|Mohan/i.test(vName)) {
        score += 220;
      } else if (gen === 'female' && indianFemaleRegex.test(vName)) {
        score += 140;
      } else if (gen === 'male' && indianMaleRegex.test(vName)) {
        score += 140;
      } else if (/IN$/i.test(vLang)) {
        score += 110;
      }
    } else if (lang === 'mr') {
      if (/^mr/i.test(vLang) || /Marathi|मराठी|Aarohi|Manohar/i.test(vName)) {
        score += 220;
      } else if (/^hi/i.test(vLang) || /Google हिन्दी|Swara|Kalpana|Madhur|Hemant/i.test(vName)) {
        // Devanagari script is shared between Marathi & Hindi, so hi-IN reads Marathi naturally
        score += 180;
      } else if (gen === 'female' && indianFemaleRegex.test(vName)) {
        score += 130;
      } else if (gen === 'male' && indianMaleRegex.test(vName)) {
        score += 130;
      }
    } else if (lang === 'hi') {
      if (/^hi/i.test(vLang) || /Hindi|हिन्दी|Swara|Kalpana|Madhur|Hemant/i.test(vName)) {
        score += 220;
      } else if (gen === 'female' && indianFemaleRegex.test(vName)) {
        score += 145;
      } else if (gen === 'male' && indianMaleRegex.test(vName)) {
        score += 145;
      } else if (/IN$/i.test(vLang)) {
        score += 115;
      }
    } else {
      // English ('en') with Accent ('IN', 'US', 'GB')
      if (acc === 'IN') {
        if (/^en-IN/i.test(vLang) || /Heera|Neerja|Ravi|Prabhat|India/i.test(vName)) {
          score += 220;
        } else if (gen === 'female' && (/Google हिन्दी/i.test(vName) || indianFemaleRegex.test(vName))) {
          // Chrome's built-in Google हिन्दी (hi-IN) is a genuine Indian Lady neural voice that speaks English with an authentic Indian accent
          score += 175;
        } else if (gen === 'male' && indianMaleRegex.test(vName)) {
          score += 165;
        } else if (/^en-GB/i.test(vLang) || /Hazel|UK English/i.test(vName)) {
          score += 95;
        } else if (/^en/i.test(vLang)) {
          score += 70;
        }
      } else if (acc === 'GB') {
        if (/^en-GB/i.test(vLang) || /UK English|Great Britain|Hazel|Sonia|Ryan|George/i.test(vName)) {
          score += 200;
        } else if (/^en/i.test(vLang)) {
          score += 80;
        }
      } else {
        // US Accent
        if (/^en-US/i.test(vLang) || /US English|United States|Zira|David|Aria|Jenny|Guy/i.test(vName)) {
          score += 200;
        } else if (/^en/i.test(vLang)) {
          score += 80;
        }
      }
    }

    if (/Natural|Online|Google/i.test(vName)) {
      score += 15;
    }

    if (score > bestScore) {
      bestScore = score;
      bestVoice = v;
    }
  }

  return bestVoice || voices[0] || null;
}

function setAfccVoiceLanguage(lang) {
  const clean = String(lang || 'en').toLowerCase();
  if (['en', 'hi', 'te', 'mr'].includes(clean)) {
    window.AFCCVoice.voiceLanguage = clean;
    if (clean !== 'en') {
      window.AFCCVoice.voiceAccent = 'IN';
    }
    try {
      localStorage.setItem('afcc_voice_lang', clean);
      localStorage.setItem('afcc_voice_accent', window.AFCCVoice.voiceAccent);
    } catch (e) {}
    syncVoiceProfileSelectors();
    if (window.AFCCVoice.isListening) {
      startBrowserSpeechRecognition();
    }
  }
}

function setAfccVoiceGender(gender) {
  const clean = String(gender || 'female').toLowerCase() === 'male' ? 'male' : 'female';
  window.AFCCVoice.voiceGender = clean;
  try {
    localStorage.setItem('afcc_voice_gender', clean);
  } catch (e) {}
  syncVoiceProfileSelectors();
}

function setAfccVoiceAccent(accent) {
  const clean = String(accent || 'IN').toUpperCase();
  if (['IN', 'US', 'GB'].includes(clean)) {
    window.AFCCVoice.voiceAccent = clean;
    try {
      localStorage.setItem('afcc_voice_accent', clean);
    } catch (e) {}
    syncVoiceProfileSelectors();
    if (window.AFCCVoice.isListening) {
      startBrowserSpeechRecognition();
    }
  }
}

function testAfccSelectedVoice() {
  const lang = String(window.AFCCVoice.voiceLanguage || 'en').toLowerCase();
  const gen = String(window.AFCCVoice.voiceGender || 'female').toLowerCase();
  const acc = String(window.AFCCVoice.voiceAccent || 'IN').toUpperCase();

  let nativeSample = '';
  let phoneticSample = '';

  if (lang === 'hi') {
    nativeSample = gen === 'male'
      ? 'नमस्ते! मैं आपका पर्सनल एजेंटिक फ्लीट वॉयस कोपायलट हूँ। आज मैं आपकी क्या सहायता कर सकता हूँ?'
      : 'नमस्ते! मैं आपकी पर्सनल एजेंटिक फ्लीट वॉयस कोपायलट हूँ। आज मैं आपकी क्या सहायता कर सकती हूँ?';
    phoneticSample = gen === 'male'
      ? 'Namaste! Main aapka Personal Agentic Fleet Voice Copilot hoon. Aaj main aapki kya sahayata kar sakta hoon?'
      : 'Namaste! Main aapki Personal Agentic Fleet Voice Copilot hoon. Aaj main aapki kya sahayata kar sakti hoon?';
  } else if (lang === 'te') {
    nativeSample = 'నమస్కారం! నేను మీ పర్సనల్ ఏజెంటిక్ ఫ్లీట్ వాయిస్ కోపైలట్ ని. ఈ రోజు నేను మీకు ఎలా సహాయం చేయగలను?';
    phoneticSample = 'Namaskaram! Nenu mee Personal Agentic Fleet Voice Copilot ni. Ee roju nenu meeku ela sahayam cheyagalanu?';
  } else if (lang === 'mr') {
    nativeSample = gen === 'male'
      ? 'नमस्कार! मी तुमचा पर्सनल एजेंटिक फ्लीट व्हॉइस कोपायलट आहे. आज मी तुम्हाला कशी मदत करू शकतो?'
      : 'नमस्कार! मी तुमची पर्सनल एजेंटिक फ्लीट व्हॉइस कोपायलट आहे. आज मी तुम्हाला कशी मदत करू शकते?';
    phoneticSample = gen === 'male'
      ? 'Namaskar! Mi tumcha Personal Agentic Fleet Voice Copilot aahe. Aaj mi tumhala kashi madat karu shakto?'
      : 'Namaskar! Mi tumchi Personal Agentic Fleet Voice Copilot aahe. Aaj mi tumhala kashi madat karu shakte?';
  } else {
    const accLabel = acc === 'IN' ? 'Indian English' : (acc === 'GB' ? 'British English' : 'US English');
    const greeting = acc === 'IN' ? 'Namaste!' : 'Hello!';
    nativeSample = `${greeting} I am your Personal Agentic Fleet Voice Copilot, speaking in an ${accLabel} ${gen === 'male' ? 'male' : 'lady'} voice. How can I help you today?`;
    phoneticSample = nativeSample;
  }

  const replyLineEl = document.getElementById('voiceAssistantReplyLine');
  const replyTextEl = document.getElementById('voiceSpokenReplyText');
  if (replyLineEl && replyTextEl) {
    replyLineEl.style.display = 'block';
    replyTextEl.textContent = nativeSample;
  }
  speakAfccVoiceText(nativeSample, null, phoneticSample);
}

if ('speechSynthesis' in window && typeof window.speechSynthesis.onvoiceschanged !== 'undefined') {
  window.speechSynthesis.onvoiceschanged = () => {
    syncVoiceProfileSelectors();
  };
}

function updateVoiceCopilotUI(stateLabel, stateKind) {
  const badge = document.getElementById('voiceStateBadge');
  const orb = document.getElementById('voiceHudOrb');
  const btnMic = document.getElementById('btnVoiceToggleMic');
  const btnInputMic = document.getElementById('btnAgVoiceMic');
  const btnGlobalVoice = document.getElementById('btnGlobalVoiceLive');
  const globalBtnText = document.getElementById('globalVoiceBtnText');
  const btnCont = document.getElementById('btnVoiceContinuousMode');
  const btnTts = document.getElementById('btnVoiceTtsToggle');
  const btnStopSpeak = document.getElementById('btnVoiceStopSpeaking');

  const isListening = Boolean(window.AFCCVoice.isListening);
  const isSpeaking = Boolean(window.AFCCVoice.isSpeaking);

  if (badge) {
    if (stateLabel) {
      badge.textContent = stateLabel;
    } else if (isListening) {
      badge.textContent = '🎙️ Listening to you...';
    } else if (isSpeaking) {
      badge.textContent = '🔊 AFCC Speaking...';
    } else {
      badge.textContent = '● Ready to Listen & Speak';
    }
    if (stateKind === 'listening' || isListening) {
      badge.style.background = 'rgba(244, 63, 94, 0.2)';
      badge.style.color = '#fb7185';
      badge.style.borderColor = 'rgba(244, 63, 94, 0.45)';
    } else if (stateKind === 'speaking' || isSpeaking) {
      badge.style.background = 'rgba(56, 189, 248, 0.2)';
      badge.style.color = '#38bdf8';
      badge.style.borderColor = 'rgba(56, 189, 248, 0.45)';
    } else if (stateKind === 'executing') {
      badge.style.background = 'rgba(245, 158, 11, 0.2)';
      badge.style.color = '#fbbf24';
      badge.style.borderColor = 'rgba(245, 158, 11, 0.45)';
    } else {
      badge.style.background = 'rgba(16, 185, 129, 0.16)';
      badge.style.color = '#34d399';
      badge.style.borderColor = 'rgba(16, 185, 129, 0.35)';
    }
  }

  if (orb) {
    orb.textContent = isListening ? '🔴' : (isSpeaking ? '🔊' : '🎙️');
    orb.style.boxShadow = (isListening || isSpeaking) ? '0 0 14px rgba(168, 85, 247, 0.75)' : 'none';
  }

  if (btnMic) {
    btnMic.innerHTML = isListening ? '⏹️ Stop Mic' : '🎙️ Speak Now';
    btnMic.style.background = isListening
      ? 'linear-gradient(135deg, #ef4444, #dc2626)'
      : 'linear-gradient(135deg, #a855f7, #6366f1)';
  }

  if (btnInputMic) {
    btnInputMic.style.background = isListening ? 'rgba(239, 68, 68, 0.25)' : 'rgba(168, 85, 247, 0.14)';
    btnInputMic.style.borderColor = isListening ? '#ef4444' : 'rgba(168, 85, 247, 0.45)';
    btnInputMic.style.color = isListening ? '#fca5a5' : '#d8b4fe';
  }

  if (btnGlobalVoice && globalBtnText) {
    globalBtnText.textContent = isListening ? 'Listening...' : (isSpeaking ? 'Speaking...' : 'Voice Live');
    btnGlobalVoice.style.background = isListening
      ? 'rgba(239, 68, 68, 0.22)'
      : 'rgba(168, 85, 247, 0.16)';
    btnGlobalVoice.style.borderColor = isListening ? '#ef4444' : 'rgba(168, 85, 247, 0.5)';
  }

  if (btnCont) {
    const cOn = Boolean(window.AFCCVoice.continuousMode);
    btnCont.innerHTML = cOn ? '🔄 Hands-Free: ON' : '🔄 Hands-Free: OFF';
    btnCont.style.color = cOn ? '#34d399' : 'var(--text-muted)';
    btnCont.style.borderColor = cOn ? 'rgba(16, 185, 129, 0.45)' : 'var(--card-border)';
    btnCont.style.background = cOn ? 'rgba(16, 185, 129, 0.14)' : 'rgba(255, 255, 255, 0.04)';
  }

  if (btnTts) {
    const tOn = Boolean(window.AFCCVoice.spokenReplyEnabled);
    btnTts.innerHTML = tOn ? '🔊 Voice Reply: ON' : '🔇 Voice Reply: OFF';
    btnTts.style.color = tOn ? 'var(--accent-cyan)' : 'var(--text-muted)';
    btnTts.style.borderColor = tOn ? 'rgba(56, 189, 248, 0.4)' : 'var(--card-border)';
    btnTts.style.background = tOn ? 'rgba(56, 189, 248, 0.12)' : 'rgba(255, 255, 255, 0.04)';
  }

  if (btnStopSpeak) {
    btnStopSpeak.style.display = isSpeaking ? 'inline-flex' : 'none';
  }
  syncVoiceProfileSelectors();
}

function toggleVoiceCopilotPanel(startListeningImmediately) {
  const hud = document.getElementById('afccVoiceCopilotHud');
  if (!window.isAgRightDocked && typeof openAntigravityRightDock === 'function') {
    openAntigravityRightDock();
  }
  if (hud) {
    const isHidden = hud.style.display === 'none';
    hud.style.display = (startListeningImmediately || isHidden) ? 'block' : 'none';
  }
  updateVoiceCopilotUI();
  if (startListeningImmediately && !window.AFCCVoice.isListening) {
    toggleVoiceMicListening(true);
  }
}

function toggleVoiceContinuousLoop() {
  window.AFCCVoice.continuousMode = !window.AFCCVoice.continuousMode;
  try {
    localStorage.setItem('afcc_voice_continuous', window.AFCCVoice.continuousMode ? 'true' : 'false');
  } catch (e) {}
  updateVoiceCopilotUI();
}

function toggleVoiceSpokenReply() {
  window.AFCCVoice.spokenReplyEnabled = !window.AFCCVoice.spokenReplyEnabled;
  try {
    localStorage.setItem('afcc_voice_tts_enabled', window.AFCCVoice.spokenReplyEnabled ? 'true' : 'false');
  } catch (e) {}
  if (!window.AFCCVoice.spokenReplyEnabled) {
    stopAfccVoiceSpeaking();
  }
  updateVoiceCopilotUI();
}

function setAfccVoiceRate(val) {
  const num = parseFloat(val);
  if (!isNaN(num) && num >= 0.5 && num <= 2.0) {
    window.AFCCVoice.speechRate = num;
    try {
      localStorage.setItem('afcc_voice_rate', String(num));
    } catch (e) {}
  }
}

function stopAfccVoiceSpeaking() {
  if ('speechSynthesis' in window) {
    try {
      window.speechSynthesis.cancel();
    } catch (e) {}
  }
  window.AFCCVoice.isSpeaking = false;
  updateVoiceCopilotUI();
}

function speakAfccVoiceText(text, onDoneCallback, altPhoneticText) {
  const cleanText = String(text || '').trim();
  if (!cleanText) {
    if (typeof onDoneCallback === 'function') onDoneCallback();
    return;
  }
  window.AFCCVoice.lastSpokenReply = cleanText;
  window.AFCCVoice.lastSpokenPhonetic = String(altPhoneticText || cleanText).trim();

  if (!window.AFCCVoice.spokenReplyEnabled || !('speechSynthesis' in window)) {
    if (typeof onDoneCallback === 'function') onDoneCallback();
    return;
  }

  try {
    window.speechSynthesis.cancel();
    const langCode = String(window.AFCCVoice.voiceLanguage || 'en').toLowerCase();
    const gender = String(window.AFCCVoice.voiceGender || 'female').toLowerCase();
    const accent = String(window.AFCCVoice.voiceAccent || 'IN').toUpperCase();
    const targetBcp47 = getTargetVoiceLocale();

    const voices = window.speechSynthesis.getVoices ? window.speechSynthesis.getVoices() : [];
    const preferred = resolveBestSpeechVoice(voices, langCode, gender, accent);

    // If speaking Telugu/Hindi/Marathi and the selected voice does not support the native script, use phonetic text so it speaks aloud clearly
    let spokenPayload = cleanText;
    if (preferred && altPhoneticText) {
      const vLang = String(preferred.lang || '').toLowerCase();
      const vName = String(preferred.name || '');
      if (langCode === 'te' && !vLang.startsWith('te') && !/telugu|తెలుగు|shruti|mohan/i.test(vName)) {
        spokenPayload = String(altPhoneticText).trim();
      } else if ((langCode === 'hi' || langCode === 'mr') && !vLang.startsWith('hi') && !vLang.startsWith('mr') && !/hindi|marathi|हिन्दी|मराठी|swara|kalpana|aarohi|madhur|hemant|manohar/i.test(vName)) {
        spokenPayload = String(altPhoneticText).trim();
      }
    }

    const utter = new SpeechSynthesisUtterance(spokenPayload);
    utter.rate = window.AFCCVoice.speechRate || 1.05;
    utter.lang = preferred && preferred.lang ? preferred.lang : targetBcp47;

    if (preferred) {
      utter.voice = preferred;
      const vName = String(preferred.name || '');
      if (gender === 'female' && /\bMale\b|David|Guy|Ravi|Prabhat|Madhur|Mohan|Manohar|Hemant/i.test(vName)) {
        utter.pitch = 1.18;
      } else if (gender === 'male' && /Female|Zira|Hazel|Heera|Neerja|Swara|Shruti|Aarohi|Kalpana|Google हिन्दी/i.test(vName)) {
        utter.pitch = 0.85;
      } else {
        utter.pitch = gender === 'female' ? 1.04 : 0.94;
      }
    } else {
      utter.pitch = gender === 'female' ? 1.06 : 0.92;
    }

    utter.onstart = () => {
      window.AFCCVoice.isSpeaking = true;
      updateVoiceCopilotUI(`🔊 Speaking (${getVoiceProfileDisplayLabel()})...`, 'speaking');
    };
    utter.onend = () => {
      window.AFCCVoice.isSpeaking = false;
      updateVoiceCopilotUI();
      if (typeof onDoneCallback === 'function') onDoneCallback();
    };
    utter.onerror = () => {
      window.AFCCVoice.isSpeaking = false;
      updateVoiceCopilotUI();
      if (typeof onDoneCallback === 'function') onDoneCallback();
    };

    window.speechSynthesis.speak(utter);
  } catch (e) {
    window.AFCCVoice.isSpeaking = false;
    updateVoiceCopilotUI();
    if (typeof onDoneCallback === 'function') onDoneCallback();
  }
}

function replayLastAfccVoiceReply() {
  if (window.AFCCVoice.lastSpokenReply) {
    speakAfccVoiceText(
      window.AFCCVoice.lastSpokenReply,
      null,
      window.AFCCVoice.lastSpokenPhonetic || window.AFCCVoice.lastSpokenReply
    );
  }
}

async function executeVoiceUiActions(uiActions) {
  if (!Array.isArray(uiActions) || uiActions.length === 0) return;
  for (const act of uiActions) {
    if (!act || !act.type) continue;
    try {
      if (act.type === 'switch_agent' && act.agent_id) {
        if (typeof FleetNavigator !== 'undefined' && typeof FleetNavigator.switchAgent === 'function') {
          FleetNavigator.switchAgent(act.agent_id);
        } else if (typeof switchTab === 'function') {
          switchTab(act.agent_id);
        }
      } else if (act.type === 'send_to_antigravity' && act.command) {
        if (typeof setAgChatEngineMode === 'function') {
          setAgChatEngineMode('antigravity_live');
        }
        const cmdInput = document.getElementById('agCommandInput');
        if (cmdInput) {
          cmdInput.value = String(act.command);
          if (typeof submitAgCommand === 'function') {
            setTimeout(() => submitAgCommand(), 100);
          }
        }
      } else if (act.type === 'play_video_by_voice') {
        if (typeof FleetNavigator !== 'undefined' && typeof FleetNavigator.switchAgent === 'function') {
          FleetNavigator.switchAgent('health');
        }
        setTimeout(() => {
          const q = String(act.query || '').toLowerCase();
          if (q.includes('playlist') || q.includes('routine') || !q) {
            if (typeof playSelectedPlaylist === 'function') playSelectedPlaylist();
          } else if (Array.isArray(window._allExerciseVideos) && window._allExerciseVideos.length > 0) {
            const match = window._allExerciseVideos.find(v =>
              String(v.title || '').toLowerCase().includes(q) ||
              String(v.category || '').toLowerCase().includes(q)
            ) || window._allExerciseVideos[0];
            if (match && typeof playExerciseVideo === 'function') {
              playExerciseVideo(match.filename, match.title, match.category);
            }
          } else if (typeof playSelectedPlaylist === 'function') {
            playSelectedPlaylist();
          }
        }, 250);
      } else if (act.type === 'auto_tune_pc') {
        if (typeof runCompleteOptimization === 'function') {
          runCompleteOptimization();
        } else if (typeof fetchOptimizerData === 'function') {
          fetchOptimizerData();
        }
      } else if (act.type === 'filter_tasks' && act.filter) {
        if (typeof filterTasksBySource === 'function') {
          await fetchTasks();
          filterTasksBySource(act.filter);
        }
      } else if (act.type === 'set_task_mask') {
        window._maskSensitiveTaskData = Boolean(act.masked);
        try {
          localStorage.setItem('afcc_mask_sensitive_tasks', window._maskSensitiveTaskData ? 'true' : 'false');
        } catch (e) {}
        if (typeof renderTasksList === 'function') renderTasksList();
        if (typeof fetchTasks === 'function') fetchTasks();
      } else if (act.type === 'refresh_tasks') {
        if (typeof fetchTasks === 'function') fetchTasks();
      } else if (act.type === 'refresh_briefing') {
        if (typeof fetchBriefing === 'function') fetchBriefing();
      } else if (act.type === 'refresh_health') {
        if (typeof fetchHealthDashboard === 'function') fetchHealthDashboard();
      } else if (act.type === 'refresh_emails') {
        if (typeof syncEmails === 'function') syncEmails();
        else if (typeof fetchEmails === 'function') fetchEmails();
        if (typeof fetchEmailProposals === 'function') fetchEmailProposals();
      } else if (act.type === 'test_virus_shield') {
        if (typeof testAttachmentVirusShield === 'function') testAttachmentVirusShield();
      } else if (act.type === 'refresh_optimizer') {
        if (typeof fetchOptimizerData === 'function') fetchOptimizerData();
      } else if (act.type === 'run_security_scan') {
        if (typeof runSecurityScanFromHeader === 'function') runSecurityScanFromHeader();
      } else if (act.type === 'run_tests') {
        if (typeof runTestsNow === 'function') runTestsNow();
      } else if (act.type === 'filter_backlog' && act.status) {
        setTimeout(() => {
          if (typeof filterBacklogByStatus === 'function') filterBacklogByStatus(act.status);
        }, 120);
      } else if (act.type === 'open_evolve_modal' && act.agent_id) {
        if (typeof openEvolveAgentModal === 'function') openEvolveAgentModal(act.agent_id);
      } else if (act.type === 'set_theme' && act.theme) {
        if (typeof FleetNavigator !== 'undefined') {
          FleetNavigator.themeMode = act.theme;
          FleetNavigator.savePersistedState();
          FleetNavigator.applyLayoutAndThemeToDOM();
        }
      } else if (act.type === 'set_layout' && act.layout) {
        if (typeof FleetNavigator !== 'undefined' && typeof FleetNavigator.setWorkspaceLayout === 'function') {
          FleetNavigator.setWorkspaceLayout(act.layout, true);
        }
      }
    } catch (err) {
      console.warn('Voice UI action error:', err);
    }
  }
}

async function executeVoiceTurnText(transcriptText, alternativesList) {
  const rawAlts = Array.isArray(alternativesList) && alternativesList.length > 0
    ? alternativesList
    : [transcriptText];
  const spoken = selectBestJarvisClientAlternative(rawAlts) || String(transcriptText || '').trim();
  if (!spoken) return;

  const transcriptEl = document.getElementById('voiceTranscriptText');
  const replyLineEl = document.getElementById('voiceAssistantReplyLine');
  const replyTextEl = document.getElementById('voiceSpokenReplyText');
  const actStripEl = document.getElementById('voiceExecutedActivitiesStrip');

  if (transcriptEl) {
    transcriptEl.innerHTML = `<strong style="color: #fff;">"${escapeHtml(spoken)}"</strong>`;
  }
  updateVoiceCopilotUI('⚡ J.A.R.V.I.S. Processing...', 'executing');

  try {
    const res = await fetch('/api/voice/converse', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        transcript: spoken,
        alternatives: rawAlts,
        routing_mode: window.AFCCVoice.routingMode || 'zero_token',
        language: window.AFCCVoice.voiceLanguage || 'en',
        gender: window.AFCCVoice.voiceGender || 'female',
        accent: window.AFCCVoice.voiceAccent || 'IN'
      })
    });
    const data = await res.json();

    if (data.selected_transcript && data.selected_transcript !== spoken && transcriptEl) {
      transcriptEl.innerHTML = `<strong style="color: #fff;">"${escapeHtml(data.selected_transcript)}"</strong> <span style="font-size: 10px; color: #34d399;">(Acoustic Match)</span>`;
    }

    // If the utterance was rejected as background noise at $0.00, do not speak gibberish
    if (data.ignored_noise) {
      if (replyLineEl && replyTextEl) {
        replyLineEl.style.display = 'block';
        replyTextEl.textContent = data.message || `🛡️ Filtered background noise ("${spoken}") — $0.00 (0 tokens).`;
      }
      updateVoiceCopilotUI('🛡️ Filtered Background Noise ($0.00)', 'ready');
      if (window.AFCCVoice.userWantsListening && window.AFCCVoice.continuousMode) {
        setTimeout(() => startBrowserSpeechRecognition(), 250);
      }
      return;
    }

    let spokenReply = data.spoken_reply || data.message || data.title || 'Done.';
    // Client-side safety shield: never display or speak raw JSON telemetry
    if (typeof spokenReply === 'string' && spokenReply.trim().startsWith('{') && spokenReply.includes('conversation')) {
      spokenReply = 'I heard you clearly. All Fleet agents are online at $0.00 zero-token cost. Tell me which agent or action you would like to run.';
    }
    const spokenPhonetic = data.spoken_reply_phonetic || spokenReply;
    if (replyLineEl && replyTextEl) {
      replyLineEl.style.display = 'block';
      replyTextEl.textContent = spokenReply;
    }

    const activities = Array.isArray(data.executed_activities) ? data.executed_activities : [];
    if (actStripEl) {
      if (activities.length > 0) {
        actStripEl.style.display = 'flex';
        actStripEl.innerHTML = activities.map(act => `
          <span class="badge" style="background: rgba(16, 185, 129, 0.16); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.35); font-size: 10px; padding: 2px 7px;">
            ⚡ ${escapeHtml(act)}
          </span>
        `).join('');
      } else {
        actStripEl.style.display = 'none';
      }
    }

    // Mirror into Zero-Token Fleet Chat history so conversation is preserved visually
    if (typeof FleetNavigator !== 'undefined') {
      if (!Array.isArray(FleetNavigator.omnibarChatTurns)) {
        FleetNavigator.omnibarChatTurns = [];
      }
      FleetNavigator.omnibarChatTurns.push({
        userQuery: `🎙️ ${data.selected_transcript || spoken}`,
        data: data
      });
      if (typeof renderAgFleetZeroChat === 'function') {
        renderAgFleetZeroChat();
      }
    }

    // Execute linked live UI & agent activities simultaneously
    await executeVoiceUiActions(data.ui_actions || []);
    if (typeof fetchLogs === 'function') fetchLogs();

    // Speak the reply aloud and resume listening if in continuous hands-free mode
    speakAfccVoiceText(spokenReply, () => {
      if (window.AFCCVoice.userWantsListening && window.AFCCVoice.continuousMode) {
        startBrowserSpeechRecognition();
      }
    }, spokenPhonetic);
  } catch (e) {
    console.error('Voice converse error:', e);
    updateVoiceCopilotUI();
  }
}

async function startBrowserSpeechRecognition() {
  const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
  const transcriptEl = document.getElementById('voiceTranscriptText');
  if (!SpeechRec) {
    if (transcriptEl) {
      transcriptEl.innerHTML = `<span style="color: #fbbf24;">Browser SpeechRecognition unavailable — click any Jarvis chip below or type in the console!</span>`;
    }
    window.AFCCVoice.isListening = false;
    window.AFCCVoice.userWantsListening = false;
    updateVoiceCopilotUI();
    return;
  }

  // Stop any ongoing TTS before listening to avoid self-echo
  if (window.AFCCVoice.isSpeaking) {
    stopAfccVoiceSpeaking();
  }

  // Start persistent WebAudio DSP Bandpass (85Hz-3800Hz) & Biometric Pitch Analyzer
  // IMPORTANT: Do NOT open and immediately stop getUserMedia tracks before rec.start(),
  // as stopping tracks causes a 1.2s Windows WASAPI reset that clips the start of user speech.
  await ensureJarvisAudioDspPipeline();

  window.AFCCVoice.utterancePitchSamples = [];
  window.AFCCVoice.utteranceCentroidSamples = [];
  window.AFCCVoice.utterancePeakSnrDb = 0;

  try {
    if (window.AFCCVoice.recognition) {
      try { window.AFCCVoice.recognition.abort(); } catch (e) {}
    }
    const rec = new SpeechRec();
    const targetBcp47 = getTargetVoiceLocale();
    rec.lang = targetBcp47;
    rec.interimResults = true;
    rec.maxAlternatives = 5;
    rec.continuous = false;

    let finalTranscript = '';
    let collectedAlternatives = [];

    rec.onstart = () => {
      window.AFCCVoice.isListening = true;
      updateVoiceCopilotUI(`🎙️ J.A.R.V.I.S. Listening (${targetBcp47})...`, 'listening');
      if (transcriptEl) {
        transcriptEl.innerHTML = `<span style="color: #c084fc; font-style: italic;">J.A.R.V.I.S. listening (${escapeHtml(getVoiceProfileDisplayLabel())})... Speak your command now.</span>`;
      }
    };

    rec.onresult = (event) => {
      let interim = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const resItem = event.results[i];
        const alts = [];
        for (let k = 0; k < resItem.length; k++) {
          if (resItem[k] && resItem[k].transcript) {
            alts.push(String(resItem[k].transcript).trim());
          }
        }
        const bestChunk = selectBestJarvisClientAlternative(alts) || (resItem[0] ? resItem[0].transcript : '');
        if (resItem.isFinal) {
          finalTranscript += (finalTranscript ? ' ' : '') + bestChunk;
          collectedAlternatives = alts.length > 0 ? alts : [bestChunk];
        } else {
          interim += bestChunk;
        }
      }
      const preview = (finalTranscript || interim || '').trim();
      if (preview && transcriptEl) {
        transcriptEl.innerHTML = `<span style="color: #e2e8f0;">"${escapeHtml(preview)}"</span>`;
      }
    };

    rec.onerror = (event) => {
      window.AFCCVoice.isListening = false;
      if (event && (event.error === 'not-allowed' || event.error === 'service-not-allowed')) {
        window.AFCCVoice.userWantsListening = false;
        stopJarvisAudioDspPipeline();
        if (transcriptEl) {
          transcriptEl.innerHTML = `<span style="color: #fb7185;">Microphone permission blocked (${escapeHtml(event.error)}). Allow microphone access in browser settings or click any Jarvis command chip below.</span>`;
        }
      } else if (event && event.error === 'audio-capture') {
        window.AFCCVoice.userWantsListening = false;
        stopJarvisAudioDspPipeline();
        if (transcriptEl) {
          transcriptEl.innerHTML = `<span style="color: #fbbf24;">No active microphone hardware detected by Windows. Connect a microphone or click any Jarvis command chip below.</span>`;
        }
      }
      updateVoiceCopilotUI();
    };

    rec.onend = () => {
      window.AFCCVoice.isListening = false;
      updateVoiceCopilotUI();
      const captured = finalTranscript.trim();
      if (captured) {
        // Biometric Speaker Verification & Background Noise Gate
        const bioCheck = verifySpeakerBiometrics(captured, collectedAlternatives);
        if (!bioCheck.allowed) {
          if (transcriptEl) {
            transcriptEl.innerHTML = `<span style="color: #fbbf24;">🛡️ ${escapeHtml(bioCheck.reason || 'Background audio ignored')} ("${escapeHtml(captured)}")</span>`;
          }
          updateVoiceCopilotUI('🛡️ Speaker Lock: Filtered Background Audio', 'ready');
          if (window.AFCCVoice.userWantsListening && window.AFCCVoice.continuousMode && !window.AFCCVoice.isSpeaking) {
            setTimeout(() => startBrowserSpeechRecognition(), 300);
          }
          return;
        }
        executeVoiceTurnText(captured, collectedAlternatives);
      } else if (window.AFCCVoice.userWantsListening && window.AFCCVoice.continuousMode && !window.AFCCVoice.isSpeaking) {
        setTimeout(() => {
          if (window.AFCCVoice.userWantsListening && !window.AFCCVoice.isListening && !window.AFCCVoice.isSpeaking) {
            startBrowserSpeechRecognition();
          }
        }, 350);
      }
    };

    window.AFCCVoice.recognition = rec;
    rec.start();
  } catch (e) {
    window.AFCCVoice.isListening = false;
    updateVoiceCopilotUI();
  }
}

function toggleVoiceMicListening(forceStart) {
  const shouldStart = typeof forceStart === 'boolean' ? forceStart : !window.AFCCVoice.isListening;
  if (shouldStart) {
    window.AFCCVoice.userWantsListening = true;
    startBrowserSpeechRecognition();
  } else {
    window.AFCCVoice.userWantsListening = false;
    window.AFCCVoice.isListening = false;
    if (window.AFCCVoice.recognition) {
      try { window.AFCCVoice.recognition.stop(); } catch (e) {}
    }
    stopJarvisAudioDspPipeline();
    updateVoiceCopilotUI();
  }
}

window.toggleVoiceCopilotPanel = toggleVoiceCopilotPanel;
window.toggleVoiceMicListening = toggleVoiceMicListening;
window.toggleVoiceContinuousLoop = toggleVoiceContinuousLoop;
window.toggleVoiceSpokenReply = toggleVoiceSpokenReply;
window.stopAfccVoiceSpeaking = stopAfccVoiceSpeaking;
window.setAfccVoiceRate = setAfccVoiceRate;
window.setAfccVoiceLanguage = setAfccVoiceLanguage;
window.setAfccVoiceGender = setAfccVoiceGender;
window.setAfccVoiceAccent = setAfccVoiceAccent;
window.setAfccVoiceRoutingMode = setAfccVoiceRoutingMode;
window.toggleVoiceSpeakerLock = toggleVoiceSpeakerLock;
window.toggleVoiceWakeWordLock = toggleVoiceWakeWordLock;
window.calibrateJarvisVoiceprint = calibrateJarvisVoiceprint;
window.verifySpeakerBiometrics = verifySpeakerBiometrics;
window.testAfccSelectedVoice = testAfccSelectedVoice;
window.resolveBestSpeechVoice = resolveBestSpeechVoice;
window.getTargetVoiceLocale = getTargetVoiceLocale;
window.replayLastAfccVoiceReply = replayLastAfccVoiceReply;
window.executeVoiceTurnText = executeVoiceTurnText;
window.executeVoiceUiActions = executeVoiceUiActions;
window.speakAfccVoiceText = speakAfccVoiceText;
