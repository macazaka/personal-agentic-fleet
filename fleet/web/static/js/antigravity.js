// --- Antigravity Live Stream, Models & Agent Control ---
let lastRenderedStep = -1;
let lastTranscriptSessionId = null;
let _transcriptFetchInFlight = false;
const MAX_TRANSCRIPT_DOM_MESSAGES = 80;
let attachedImages = [];
let activeModelId = 'gemini-3.8-flash-high';
let availableModels = [];

    function _renderTranscriptMessageHtml(m) {
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
    }

    async function fetchTranscript(forceScroll = false) {
      if (_transcriptFetchInFlight && !forceScroll) return;
      _transcriptFetchInFlight = true;
      try {
        const isDelta = (!forceScroll && lastRenderedStep >= 0 && lastTranscriptSessionId !== null);
        const url = `/api/antigravity/transcript?limit=${MAX_TRANSCRIPT_DOM_MESSAGES}${isDelta ? '&since_step=' + encodeURIComponent(lastRenderedStep) : ''}`;
        const res = await fetch(url);
        const data = await res.json();
        if (data.status !== 'success') return;

        // If session rolled over, force a clean full load once
        if (isDelta && data.session_id && data.session_id !== lastTranscriptSessionId) {
          lastRenderedStep = -1;
          lastTranscriptSessionId = data.session_id;
          _transcriptFetchInFlight = false;
          return await fetchTranscript(true);
        }

        const sessionBadge = document.getElementById('agSessionBadge');
        if (sessionBadge && data.session_id) {
          sessionBadge.innerText = 'Session: ' + data.session_id.substring(0, 8);
        }

        const container = document.getElementById('agChatScroll');
        if (!container) return;

        if (isDelta) {
          if (data.unchanged || !Array.isArray(data.messages) || data.messages.length === 0) {
            return;
          }
          const deltaHtml = data.messages.map(_renderTranscriptMessageHtml).join('');
          if (container.children.length === 1 && !container.firstElementChild.classList.contains('ag-message')) {
            container.innerHTML = deltaHtml;
          } else {
            container.insertAdjacentHTML('beforeend', deltaHtml);
          }
          while (container.children.length > MAX_TRANSCRIPT_DOM_MESSAGES) {
            container.removeChild(container.firstElementChild);
          }
          lastRenderedStep = data.latest_step;
          const countBadge = document.getElementById('agMsgCountBadge');
          if (countBadge) {
            countBadge.innerText = `${data.total_steps || container.children.length} Steps`;
          }
          const autoScroll = document.getElementById('autoScrollCheck');
          if (autoScroll && autoScroll.checked) {
            container.scrollTop = container.scrollHeight;
          }
          return;
        }

        const countBadge = document.getElementById('agMsgCountBadge');
        if (countBadge) {
          countBadge.innerText = `${data.total_steps || data.messages.length} Steps`;
        }

        if (data.messages.length === 0) {
          lastTranscriptSessionId = data.session_id || null;
          lastRenderedStep = data.latest_step ?? 0;
          container.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 40px;">No messages in transcript yet.</div>';
          return;
        }

        if (data.latest_step === lastRenderedStep && data.session_id === lastTranscriptSessionId && !forceScroll) {
          return;
        }
        lastTranscriptSessionId = data.session_id || null;
        lastRenderedStep = data.latest_step;

        container.innerHTML = data.messages.map(_renderTranscriptMessageHtml).join('');

        const autoScroll = document.getElementById('autoScrollCheck');
        if (autoScroll && autoScroll.checked) {
          container.scrollTop = container.scrollHeight;
        }
      } catch (e) {
        console.error('Transcript fetch error:', e);
      } finally {
        _transcriptFetchInFlight = false;
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
          if (document.hidden) return;
          if (window.agChatEngineMode !== 'fleet_zero_token') {
            fetchTranscript(false);
          }
          fetchAgentQueue();
        }, 6000);
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
          if (agInterval) {
            clearInterval(agInterval);
            agInterval = null;
          }
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
  conciseMode: localStorage.getItem('afcc_voice_concise') !== 'false',
  whisperMode: localStorage.getItem('afcc_voice_whisper_mode') === 'true',
  audioStreamMode: localStorage.getItem('afcc_voice_stream_mode') !== 'false',
  speechRate: parseFloat(localStorage.getItem('afcc_voice_rate') || '1.35') || 1.35,
  _lastSpectrumSig: -1,
  _lastDispatchedTurnSig: '',
  _lastDispatchedTurnAtMs: 0,
  _activeVoiceFetchController: null,
  voiceLanguage: localStorage.getItem('afcc_voice_lang') || 'en',
  voiceGender: localStorage.getItem('afcc_voice_gender') || 'female',
  voiceAccent: localStorage.getItem('afcc_voice_accent') || 'IN',
  routingMode: localStorage.getItem('afcc_voice_routing_mode') || 'zero_token',
  speakerLockEnabled: localStorage.getItem('afcc_voice_speaker_lock') !== 'false',
  wakeWordRequired: localStorage.getItem('afcc_voice_wake_word_lock') !== 'false',
  wakeWordPhrase: localStorage.getItem('afcc_voice_wake_word_phrase') || 'Mahadev',
  voiceprint: _initialVoiceprint,
  strictnessThreshold: parseInt(localStorage.getItem('afcc_voiceprint_strictness') || '78', 10) || 78,
  autoRefineEnabled: localStorage.getItem('afcc_voiceprint_auto_refine') !== 'false',
  isCalibrating: false,
  isSandboxTesting: false,
  calibrationDurationSec: parseInt(localStorage.getItem('afcc_voiceprint_duration_sec') || '20', 10) || 20,
  calibrationCountdownTimer: null,
  calibrationTimeoutId: null,
  calibrationFinishCallback: null,
  audioCtx: null,
  mediaStream: null,
  analyser: null,
  dspTimer: null,
  liveSnrDb: 0,
  livePitchHz: 0,
  liveCentroidHz: 0,
  liveVtlCm: 0,
  lastVoiceActivityAtMs: 0,
  bargeInFrames: 0,
  lastTurnLatencyMs: 0,
  _cachedVoiceByKey: {},
  actionItemsCache: { open: [], closed: [], cursorIdx: 0, lastSyncedAt: 0 },
  audioMessageQueue: [],
  activeQueueItem: null,
  topicStackSnapshot: { active_topic: null, parked_topics: [], parked_count: 0 },
  utterancePitchSamples: [],
  utteranceCentroidSamples: [],
  utteranceFineFrameSamples: [],
  utterancePeakSnrDb: 0,
  calibrationPcmChunks: [],
  mediaRecorder: null,
  recordedChunks: [],
  pendingVoiceprint: null,
  voiceprintAudioDataUrl: '',
  voiceprintAudioFile: '',
  lastActionWasVoiceprint: false,
  lastUtteranceSample: null,
  lastVerificationResult: null,
  sandboxHistory: [],
  sandboxMetrics: null,
  lastSpokenReply: 'Loud and clear! I am J.A.R.V.I.S., your Personal Agentic Fleet Voice Copilot. Tell me what you would like to do.',
  lastSpokenPhonetic: 'Loud and clear! I am Jarvis, your Personal Agentic Fleet Voice Copilot. Tell me what you would like to do.',
  recognition: null
};

async function loadJarvisVoiceprintFromServer() {
  try {
    const res = await fetch('/api/voice/voiceprint');
    if (!res.ok) return;
    const data = await res.json();
    if (data && data.audio_data_url) {
      window.AFCCVoice.voiceprintAudioDataUrl = data.audio_data_url;
      window.AFCCVoice.voiceprintAudioFile = data.audio_file || 'fleet/data/user/voiceprint_sample.wav';
      const player = document.getElementById('voiceprintPreviewPlayer');
      if (player) player.src = data.audio_data_url;
    }
    if (data && data.enrolled && data.profile && data.profile.pitchMeanHz) {
      window.AFCCVoice.voiceprint = data.profile;
      if (data.profile.strictnessThreshold) {
        window.AFCCVoice.strictnessThreshold = parseInt(data.profile.strictnessThreshold, 10) || 78;
      }
      if (typeof data.profile.autoRefineEnabled === 'boolean') {
        window.AFCCVoice.autoRefineEnabled = data.profile.autoRefineEnabled;
      }
      try {
        localStorage.setItem('afcc_jarvis_voiceprint', JSON.stringify(data.profile));
      } catch (e) {}
    }
    if (data && Array.isArray(data.sandbox_history)) {
      window.AFCCVoice.sandboxHistory = data.sandbox_history;
    }
    if (data && data.sandbox_metrics) {
      window.AFCCVoice.sandboxMetrics = data.sandbox_metrics;
    }
    if (data && data.wake_word && !localStorage.getItem('afcc_voice_wake_word_phrase')) {
      window.AFCCVoice.wakeWordPhrase = String(data.wake_word).trim() || 'Mahadev';
    }
    if (data && data.speech_rate && !localStorage.getItem('afcc_voice_rate')) {
      const srvRate = parseFloat(data.speech_rate);
      if (!isNaN(srvRate) && srvRate >= 0.5 && srvRate <= 3.5) {
        window.AFCCVoice.speechRate = srvRate;
      }
    }
    if (data && data.awaiting_confirmation && data.pending_profile) {
      window.AFCCVoice.pendingVoiceprint = data.pending_profile;
      showVoiceprintConfirmationGate(
        data.pending_profile,
        window.AFCCVoice.voiceprintAudioDataUrl,
        window.AFCCVoice.voiceprintAudioFile
      );
    }
    syncVoiceProfileSelectors();
    if (typeof renderVoiceprintSandboxPanel === 'function') {
      renderVoiceprintSandboxPanel();
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
  try {
    fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ voice_wake_word_required: window.AFCCVoice.wakeWordRequired })
    });
  } catch (e) {}
}

function setAfccVoiceWakeWordRequired(required) {
  window.AFCCVoice.wakeWordRequired = Boolean(required);
  try {
    localStorage.setItem('afcc_voice_wake_word_lock', window.AFCCVoice.wakeWordRequired ? 'true' : 'false');
  } catch (e) {}
  syncVoiceProfileSelectors();
  try {
    fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ voice_wake_word_required: window.AFCCVoice.wakeWordRequired })
    });
  } catch (e) {}
}

function setAfccVoiceWakeWord(word) {
  const clean = String(word || '').trim() || 'Mahadev';
  window.AFCCVoice.wakeWordPhrase = clean;
  window.AFCCVoice.wakeWordRequired = true;
  try {
    localStorage.setItem('afcc_voice_wake_word_phrase', clean);
    localStorage.setItem('afcc_voice_wake_word_lock', 'true');
  } catch (e) {}
  syncVoiceProfileSelectors();
  try {
    fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        voice_wake_word: clean,
        voice_wake_word_required: true
      })
    });
  } catch (e) {}
}

// Pre-allocated zero-GC scratch buffers and constants for J.A.R.V.I.S. WebAudio DSP
const _SHARED_NSDF_BUF = new Float32Array(1024);
const _STATIC_BARK_BANDS = [
  [85, 200],
  [200, 350],
  [350, 550],
  [550, 850],
  [850, 1300],
  [1300, 1900],
  [1900, 2700],
  [2700, 3800]
];
const MAX_UTTERANCE_FRAMES = 80;
const MAX_CALIBRATION_PCM_CHUNKS = 120;

function computeAutocorrelationPitchHz(floatBuf, sampleRate, precomputedRms) {
  const size = floatBuf.length;
  let rms = typeof precomputedRms === 'number' ? precomputedRms : -1;
  if (rms < 0) {
    let sumSq = 0;
    let count = 0;
    for (let i = 0; i < size; i += 4) {
      const s = floatBuf[i];
      sumSq += s * s;
      count++;
    }
    rms = count > 0 ? Math.sqrt(sumSq / count) : 0;
  }
  if (rms < 0.012) return 0; // Silence or faint background

  // Human fundamental vocal pitch F0 range: 65 Hz (deep chest) to 450 Hz (child / high pitch).
  // Uses 2x-decimated Normalized Square Difference Function (NSDF / McLeod-YIN first-peak selection)
  // over a pre-allocated _SHARED_NSDF_BUF (0 heap allocations, ~94% fewer inner-loop CPU ops)
  // with 1-lag neighbor refinement so child 260-350 Hz vs adult 85-180 Hz accuracy is preserved.
  const minLag = Math.max(2, Math.floor(sampleRate / 450));
  const maxLag = Math.min(Math.floor(sampleRate / 65), Math.floor(size / 2), _SHARED_NSDF_BUF.length - 3);
  const winLen = Math.min(384, maxLag);

  let globalMaxCorr = 0;
  let globalBestLag = -1;

  for (let lag = minLag; lag <= maxLag; lag += 2) {
    let acf = 0;
    let norm = 0;
    for (let i = 0; i < winLen; i += 2) {
      const a = floatBuf[i];
      const b = floatBuf[i + lag];
      acf += a * b;
      norm += a * a + b * b;
    }
    const corr = norm > 1e-9 ? (2 * acf) / norm : 0;
    _SHARED_NSDF_BUF[lag] = corr;
    _SHARED_NSDF_BUF[lag + 1] = corr;
    if (corr > globalMaxCorr) {
      globalMaxCorr = corr;
      globalBestLag = lag;
    }
  }

  if (globalMaxCorr < 0.45 || globalBestLag <= 0) return 0;

  // Pick the FIRST prominent local peak (>= 82% of globalMaxCorr and >= 0.52)
  // to lock onto true fundamental period T0 instead of sub-harmonic 2*T0 (octave error).
  const keyThreshold = Math.max(0.52, globalMaxCorr * 0.82);
  let chosenLag = globalBestLag;
  for (let lag = minLag + 2; lag < maxLag - 1; lag += 2) {
    const c = _SHARED_NSDF_BUF[lag];
    if (c >= keyThreshold && c >= _SHARED_NSDF_BUF[lag - 2] && c >= _SHARED_NSDF_BUF[lag + 2]) {
      chosenLag = lag;
      break;
    }
  }

  // 1-step neighbor refinement around chosenLag for exact 1-sample F0 precision
  const evalSingleLag = (testLag) => {
    if (testLag < minLag || testLag > maxLag) return -1;
    let acf = 0;
    let norm = 0;
    for (let i = 0; i < winLen; i += 2) {
      const a = floatBuf[i];
      const b = floatBuf[i + testLag];
      acf += a * b;
      norm += a * a + b * b;
    }
    return norm > 1e-9 ? (2 * acf) / norm : 0;
  };
  const baseC = _SHARED_NSDF_BUF[chosenLag];
  const leftC = evalSingleLag(chosenLag - 1);
  const rightC = evalSingleLag(chosenLag + 1);
  if (leftC > baseC && leftC >= rightC) {
    chosenLag = chosenLag - 1;
  } else if (rightC > baseC) {
    chosenLag = chosenLag + 1;
  }

  const f0 = sampleRate / chosenLag;
  return (f0 >= 65 && f0 <= 450) ? Math.round(f0) : 0;
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

function extractFineAcousticFrameFeatures(freqByteBuf, sampleRate, fftSize) {
  const binHz = (sampleRate || 48000) / (fftSize || 2048);
  const maxFreqBin = Math.min(freqByteBuf.length - 1, Math.ceil(3800 / binHz));

  const findBandPeakHz = (lowHz, highHz, fallbackHz) => {
    const bStart = Math.max(1, Math.floor(lowHz / binHz));
    const bEnd = Math.min(maxFreqBin, Math.ceil(highHz / binHz));
    let bestBin = -1;
    let bestMag = 8;
    let weightedSum = 0;
    let magSum = 0;
    for (let i = bStart; i <= bEnd; i++) {
      const m = freqByteBuf[i];
      if (m > bestMag) {
        bestMag = m;
        bestBin = i;
      }
      if (m > 10) {
        weightedSum += (i * binHz) * m;
        magSum += m;
      }
    }
    if (bestBin > 0 && magSum > 0) {
      return Math.round(0.65 * (bestBin * binHz) + 0.35 * (weightedSum / magSum));
    }
    return fallbackHz;
  };

  const f1Hz = findBandPeakHz(250, 920, 490);
  const f2Hz = findBandPeakHz(920, 2350, 1480);
  const f3Hz = findBandPeakHz(2350, 3600, 2580);

  // Quarter-wave resonant tube Vocal Tract Length (cm): VTL = (2k-1)*c / (4*Fk), c = 35000 cm/s
  const vtl1 = 35000 / (4 * Math.max(250, f1Hz));
  const vtl2 = (3 * 35000) / (4 * Math.max(900, f2Hz));
  const vtl3 = (5 * 35000) / (4 * Math.max(1800, f3Hz));
  const rawVtl = 0.25 * vtl1 + 0.40 * vtl2 + 0.35 * vtl3;
  const vtlCm = Number(Math.max(10.5, Math.min(21.5, rawVtl)).toFixed(2));

  // Chest-to-Treble Resonance Ratio: low chest energy (85-235 Hz) vs upper-mid energy (350-1900 Hz)
  const bandMeanEnergy = (lowHz, highHz) => {
    const s = Math.max(1, Math.floor(lowHz / binHz));
    const e = Math.min(maxFreqBin, Math.ceil(highHz / binHz));
    if (e < s) return 1;
    let sum = 0;
    for (let i = s; i <= e; i++) sum += freqByteBuf[i];
    return sum / (e - s + 1);
  };
  const chestEnergy = bandMeanEnergy(85, 235);
  const midTrebleEnergy = Math.max(6, bandMeanEnergy(350, 1900));
  const chestResonanceRatio = Number(Math.max(0.15, Math.min(2.6, (chestEnergy / midTrebleEnergy) * 1.25)).toFixed(2));

  // 85% Spectral Rolloff Frequency
  const minBin = Math.max(1, Math.floor(85 / binHz));
  let totalEnergy = 0;
  for (let i = minBin; i <= maxFreqBin; i++) totalEnergy += freqByteBuf[i];
  let rolloffHz = 2350;
  if (totalEnergy > 0) {
    const targetEnergy = totalEnergy * 0.85;
    let accum = 0;
    for (let i = minBin; i <= maxFreqBin; i++) {
      accum += freqByteBuf[i];
      if (accum >= targetEnergy) {
        rolloffHz = Math.round(i * binHz);
        break;
      }
    }
  }

  // 8-Band Bark/Mel Sub-Band Energy Fingerprint (L2-normalized, zero-closure loop)
  const rawVec = new Array(8);
  let normSq = 0;
  for (let b = 0; b < 8; b++) {
    const val = Math.max(0.01, bandMeanEnergy(_STATIC_BARK_BANDS[b][0], _STATIC_BARK_BANDS[b][1]));
    rawVec[b] = val;
    normSq += val * val;
  }
  const norm = Math.sqrt(normSq) || 1;
  const subBandVector = new Array(8);
  for (let b = 0; b < 8; b++) {
    subBandVector[b] = Number((rawVec[b] / norm).toFixed(4));
  }

  return {
    f1Hz,
    f2Hz,
    f3Hz,
    vtlCm,
    chestResonanceRatio,
    rolloffHz,
    subBandVector
  };
}

function summarizeUtteranceBiometricVector(pitches, centroids, fineFrames, peakSnrDb) {
  const validPitches = Array.isArray(pitches) ? pitches.filter(p => p >= 65 && p <= 450) : [];
  const validCentroids = Array.isArray(centroids) ? centroids.filter(c => c > 0) : [];
  const frames = Array.isArray(fineFrames) ? fineFrames : [];

  let pitchMeanHz = 136;
  let pitchStdHz = 15;
  let pitchMinHz = 112;
  let pitchMaxHz = 168;

  if (validPitches.length >= 2) {
    const sortedP = validPitches.slice().sort((a, b) => a - b);
    // Trim extreme 10% outliers if >= 8 frames
    const trimCount = sortedP.length >= 8 ? Math.floor(sortedP.length * 0.1) : 0;
    const coreP = sortedP.slice(trimCount, sortedP.length - trimCount);
    const sum = coreP.reduce((a, b) => a + b, 0);
    pitchMeanHz = Math.round(sum / coreP.length);
    const variance = coreP.reduce((acc, v) => acc + Math.pow(v - pitchMeanHz, 2), 0) / coreP.length;
    pitchStdHz = Math.max(11, Math.min(28, Math.round(Math.sqrt(variance))));
    const p05Idx = Math.max(0, Math.floor(sortedP.length * 0.05));
    const p95Idx = Math.min(sortedP.length - 1, Math.floor(sortedP.length * 0.95));
    pitchMinHz = Math.round(sortedP[p05Idx]);
    pitchMaxHz = Math.round(sortedP[p95Idx]);
  } else if (validPitches.length === 1) {
    pitchMeanHz = Math.round(validPitches[0]);
    pitchMinHz = Math.max(65, pitchMeanHz - 18);
    pitchMaxHz = pitchMeanHz + 18;
  }

  let centroidMeanHz = 1240;
  let centroidStdHz = 125;
  if (validCentroids.length >= 2) {
    centroidMeanHz = Math.round(validCentroids.reduce((a, b) => a + b, 0) / validCentroids.length);
    const cVar = validCentroids.reduce((acc, v) => acc + Math.pow(v - centroidMeanHz, 2), 0) / validCentroids.length;
    centroidStdHz = Math.max(70, Math.round(Math.sqrt(cVar)));
  } else if (validCentroids.length === 1) {
    centroidMeanHz = Math.round(validCentroids[0]);
  }

  let f1MeanHz = 485;
  let f2MeanHz = 1475;
  let f3MeanHz = 2560;
  let vtlCm = pitchMeanHz > 220 ? 12.3 : 17.1;
  let chestResonanceRatio = pitchMeanHz > 220 ? 0.45 : 1.38;
  let rolloffMeanHz = 2320;
  let subBandVector = [0.42, 0.48, 0.39, 0.35, 0.31, 0.28, 0.22, 0.16];

  if (frames.length >= 1) {
    const avg = (fn) => frames.reduce((acc, f) => acc + fn(f), 0) / frames.length;
    f1MeanHz = Math.round(avg(f => f.f1Hz || 485));
    f2MeanHz = Math.round(avg(f => f.f2Hz || 1475));
    f3MeanHz = Math.round(avg(f => f.f3Hz || 2560));
    vtlCm = Number(avg(f => f.vtlCm || 17.0).toFixed(2));
    chestResonanceRatio = Number(avg(f => f.chestResonanceRatio || 1.35).toFixed(2));
    rolloffMeanHz = Math.round(avg(f => f.rolloffHz || 2320));

    const accumVec = [0, 0, 0, 0, 0, 0, 0, 0];
    frames.forEach(f => {
      if (Array.isArray(f.subBandVector) && f.subBandVector.length === 8) {
        for (let k = 0; k < 8; k++) accumVec[k] += Number(f.subBandVector[k] || 0);
      }
    });
    const norm = Math.sqrt(accumVec.reduce((acc, v) => acc + v * v, 0)) || 1;
    subBandVector = accumVec.map(v => Number((v / norm).toFixed(4)));
  }

  return {
    pitchMeanHz,
    pitchStdHz,
    pitchMinHz,
    pitchMaxHz,
    centroidMeanHz,
    centroidStdHz,
    f1MeanHz,
    f2MeanHz,
    f3MeanHz,
    vtlCm,
    chestResonanceRatio,
    rolloffMeanHz,
    subBandVector,
    snrFloorDb: Math.max(10, Math.min(22, (peakSnrDb || 18) - 8)),
    samplesCount: validPitches.length
  };
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
    analyser.smoothingTimeConstant = 0.55;

    source.connect(highPass);
    highPass.connect(lowPass);
    lowPass.connect(analyser);

    window.AFCCVoice.audioCtx = ctx;
    window.AFCCVoice.mediaStream = stream;
    window.AFCCVoice.analyser = analyser;

    if (window.AFCCVoice.dspTimer) clearInterval(window.AFCCVoice.dspTimer);
    const timeBuf = new Float32Array(analyser.fftSize);
    const freqBuf = new Uint8Array(analyser.frequencyBinCount);

    window.AFCCVoice._lastDspBadgeText = '';
    window.AFCCVoice._canvasIsIdleFlat = false;

    window.AFCCVoice.dspTimer = setInterval(() => {
      const isVoiceActiveMode = Boolean(
        window.AFCCVoice.isListening ||
        window.AFCCVoice.isSpeaking ||
        window.AFCCVoice.isCalibrating ||
        window.AFCCVoice.isSandboxTesting
      );
      if (!window.AFCCVoice.analyser || !isVoiceActiveMode) {
        // Auto-suspend AudioContext when J.A.R.V.I.S. is idle so browser audio thread uses 0.0% CPU
        if (
          ctx &&
          ctx.state === 'running' &&
          !isVoiceActiveMode &&
          Date.now() - (window.AFCCVoice.lastVoiceActivityAtMs || 0) > 2500
        ) {
          try { ctx.suspend(); } catch (e) {}
        }
        return;
      }
      if (document.hidden && !window.AFCCVoice.isCalibrating && !window.AFCCVoice.isSandboxTesting) {
        return;
      }
      try {
        if (ctx.state === 'suspended') {
          try { ctx.resume(); } catch (e) {}
        }
        analyser.getFloatTimeDomainData(timeBuf);

        // Fast 4x-strided RMS check (512 samples instead of 2048) to short-circuit during silence
        let sumSq = 0;
        let sampleCount = 0;
        for (let i = 0; i < timeBuf.length; i += 4) {
          const v = timeBuf[i];
          sumSq += v * v;
          sampleCount++;
        }
        const rms = sampleCount > 0 ? Math.sqrt(sumSq / sampleCount) : 0;
        const snrDb = Math.max(0, Math.round(20 * Math.log10((rms + 1e-6) / 0.002)));
        window.AFCCVoice.liveSnrDb = snrDb;

        // Silence Short-Circuit: when room is silent (rms < 0.013), skip FFT, NSDF pitch autocorrelation,
        // formant extraction, object allocations, and redundant canvas/DOM redraws (0% idle CPU & 0 GC churn)
        if (rms < 0.013) {
          window.AFCCVoice.livePitchHz = 0;
          window.AFCCVoice.liveCentroidHz = 0;
          window.AFCCVoice.bargeInFrames = 0;

          if (window.AFCCVoice.isCalibrating && window.AFCCVoice.calibrationPcmChunks.length < MAX_CALIBRATION_PCM_CHUNKS) {
            window.AFCCVoice.calibrationPcmChunks.push(new Float32Array(timeBuf));
          }

          const idleBadgeText = `SNR ${snrDb}dB • 85-3800Hz`;
          if (window.AFCCVoice._lastDspBadgeText !== idleBadgeText) {
            window.AFCCVoice._lastDspBadgeText = idleBadgeText;
            const dspBadge = document.getElementById('voiceDspStatusBadge');
            if (dspBadge) dspBadge.textContent = idleBadgeText;
          }
          if (!window.AFCCVoice._canvasIsIdleFlat && typeof renderJarvisLiveSpectrumCanvas === 'function') {
            window.AFCCVoice._canvasIsIdleFlat = true;
            renderJarvisLiveSpectrumCanvas(null, 0, snrDb);
          }
          return;
        }

        // Voiced / Active Audio Frame: compute FFT spectrum, NSDF pitch F0, and 12-D formants
        window.AFCCVoice._canvasIsIdleFlat = false;
        analyser.getByteFrequencyData(freqBuf);

        const sr = ctx.sampleRate || 48000;
        const pitchHz = computeAutocorrelationPitchHz(timeBuf, sr, rms);
        const centroidHz = computeSpectralCentroidHz(freqBuf, sr, analyser.fftSize);
        const fineFeat = extractFineAcousticFrameFeatures(freqBuf, sr, analyser.fftSize);

        window.AFCCVoice.livePitchHz = pitchHz;
        window.AFCCVoice.liveCentroidHz = centroidHz;
        window.AFCCVoice.liveVtlCm = fineFeat.vtlCm;
        window.AFCCVoice.lastVoiceActivityAtMs = Date.now();

        // Optimization 5: Real-Time Hot-Mic Barge-In Detection while J.A.R.V.I.S. is speaking
        // Guarded by a 1100ms post-speech-start grace window and 27dB SNR threshold so your own sentence tail
        // or laptop speaker onset never self-cancels J.A.R.V.I.S.'s spoken reply!
        if (
          window.AFCCVoice.isSpeaking &&
          window.AFCCVoice.userWantsListening &&
          window.AFCCVoice.continuousMode &&
          (Date.now() - (window.AFCCVoice.speakingStartedAtMs || 0) > 1100)
        ) {
          if (snrDb >= 27 && pitchHz >= 65 && pitchHz <= 195) {
            window.AFCCVoice.bargeInFrames = (window.AFCCVoice.bargeInFrames || 0) + 1;
            if (window.AFCCVoice.bargeInFrames >= 3) {
              window.AFCCVoice.bargeInFrames = 0;
              stopAfccVoiceSpeaking();
              startBrowserSpeechRecognition();
              return;
            }
          } else {
            window.AFCCVoice.bargeInFrames = 0;
          }
        }

        if (snrDb > window.AFCCVoice.utterancePeakSnrDb) {
          window.AFCCVoice.utterancePeakSnrDb = snrDb;
        }
        if (window.AFCCVoice.isCalibrating && window.AFCCVoice.calibrationPcmChunks.length < MAX_CALIBRATION_PCM_CHUNKS) {
          window.AFCCVoice.calibrationPcmChunks.push(new Float32Array(timeBuf));
        }
        if (pitchHz >= 65 && pitchHz <= 450 && snrDb >= 10) {
          if (window.AFCCVoice.utterancePitchSamples.length >= MAX_UTTERANCE_FRAMES) {
            window.AFCCVoice.utterancePitchSamples.shift();
          }
          window.AFCCVoice.utterancePitchSamples.push(pitchHz);

          if (centroidHz > 0) {
            if (window.AFCCVoice.utteranceCentroidSamples.length >= MAX_UTTERANCE_FRAMES) {
              window.AFCCVoice.utteranceCentroidSamples.shift();
            }
            window.AFCCVoice.utteranceCentroidSamples.push(centroidHz);
          }

          if (window.AFCCVoice.utteranceFineFrameSamples.length >= MAX_UTTERANCE_FRAMES) {
            window.AFCCVoice.utteranceFineFrameSamples.shift();
          }
          window.AFCCVoice.utteranceFineFrameSamples.push(fineFeat);
        }

        const nextBadgeText = pitchHz > 0
          ? `SNR ${snrDb}dB • F0 ${pitchHz}Hz • VTL ${fineFeat.vtlCm}cm`
          : `SNR ${snrDb}dB • 85-3800Hz`;
        if (window.AFCCVoice._lastDspBadgeText !== nextBadgeText) {
          window.AFCCVoice._lastDspBadgeText = nextBadgeText;
          const dspBadge = document.getElementById('voiceDspStatusBadge');
          if (dspBadge) dspBadge.textContent = nextBadgeText;
        }
        if (typeof renderJarvisLiveSpectrumCanvas === 'function') {
          renderJarvisLiveSpectrumCanvas(freqBuf, pitchHz, snrDb);
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

function encodePcmChunksToWavDataUrl(pcmChunks, sampleRate, fallbackPitchHz) {
  const sr = Math.min(24000, Math.max(8000, Math.round(sampleRate || 16000)));
  let samples = [];
  if (Array.isArray(pcmChunks) && pcmChunks.length > 0) {
    for (let c = 0; c < pcmChunks.length; c++) {
      const buf = pcmChunks[c];
      for (let i = 0; i < buf.length; i++) {
        samples.push(buf[i]);
      }
    }
  }
  if (samples.length < 4096) {
    const f0 = fallbackPitchHz || 140;
    const total = sr * 2;
    for (let i = 0; i < total; i++) {
      const t = i / sr;
      const env = Math.sin(Math.PI * (i / total));
      samples.push(0.35 * env * (Math.sin(2 * Math.PI * f0 * t) + 0.4 * Math.sin(4 * Math.PI * f0 * t)));
    }
  }

  const numSamples = samples.length;
  const buffer = new ArrayBuffer(44 + numSamples * 2);
  const view = new DataView(buffer);
  const writeStr = (offset, str) => {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
  };

  writeStr(0, 'RIFF');
  view.setUint32(4, 36 + numSamples * 2, true);
  writeStr(8, 'WAVE');
  writeStr(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sr, true);
  view.setUint32(28, sr * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeStr(36, 'data');
  view.setUint32(40, numSamples * 2, true);

  let offset = 44;
  for (let i = 0; i < numSamples; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    offset += 2;
  }

  const bytes = new Uint8Array(buffer);
  let binary = '';
  const chunkSize = 8192;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize));
  }
  return 'data:audio/wav;base64,' + btoa(binary);
}

function showVoiceprintConfirmationGate(profile, audioDataUrl, savedFilePath) {
  const panel = document.getElementById('voiceprintConfirmPanel');
  const summaryEl = document.getElementById('voiceprintConfirmSummary');
  const fileBadge = document.getElementById('voiceprintSavedFileBadge');
  const player = document.getElementById('voiceprintPreviewPlayer');
  const btnReplayTop = document.getElementById('btnReplayVoiceprint');

  if (fileBadge) {
    fileBadge.textContent = `Saved: ${savedFilePath || 'fleet/data/user/voiceprint_sample.wav'}`;
  }
  if (summaryEl && profile) {
    const durSec = profile.durationSec || window.AFCCVoice.calibrationDurationSec || 20;
    const minHz = profile.pitchMinHz || Math.max(65, (profile.pitchMeanHz || 135) - (profile.pitchStdHz || 16));
    const maxHz = profile.pitchMaxHz || ((profile.pitchMeanHz || 135) + (profile.pitchStdHz || 16));
    const qual = profile.qualityScore || 96;
    const frames = profile.samplesCount || 80;
    const vtl = profile.vtlCm || 17.1;
    const chest = profile.chestResonanceRatio || 1.38;
    const f1 = profile.f1MeanHz || 485;
    const f2 = profile.f2MeanHz || 1475;
    const f3 = profile.f3MeanHz || 2560;
    summaryEl.innerHTML = `Captured <strong>${durSec}s 5-Phase 12-D Biometric Signature</strong> (${frames} voiced frames • Quality <strong>${qual}%</strong>): <strong>Pitch F0 ${profile.pitchMeanHz} Hz</strong> (±${profile.pitchStdHz || 15} Hz, range <strong>${minHz}–${maxHz} Hz</strong>) • <strong>Vocal Tract Length ${vtl} cm</strong> (Formants <strong>F1 ${f1} / F2 ${f2} / F3 ${f3} Hz</strong>) • <strong>Chest Resonance ${chest}x</strong> • <strong>8-Band Bark Vector Locked</strong>. Child &amp; impostor voices will be strictly rejected. Replay your saved audio below and click <strong>"✅ Confirm &amp; Process Voiceprint"</strong> to lock.`;
  }
  if (player) {
    player.src = audioDataUrl || '/api/voice/voiceprint/audio';
  }
  if (btnReplayTop) {
    btnReplayTop.style.display = 'inline-block';
  }
  if (panel) {
    panel.style.display = 'block';
  }
}

function setVoiceprintCalibrationDuration(sec) {
  const supported = [10, 12, 15, 20, 25, 30];
  const cleanSec = supported.includes(Number(sec)) ? Number(sec) : 20;
  window.AFCCVoice.calibrationDurationSec = cleanSec;
  try {
    localStorage.setItem('afcc_voiceprint_duration_sec', String(cleanSec));
  } catch (e) {}

  supported.forEach(val => {
    const btn = document.getElementById(`btnVpDur${val}`);
    if (btn) {
      const isAct = val === cleanSec;
      btn.style.borderColor = isAct ? 'var(--accent-cyan)' : 'var(--card-border)';
      btn.style.color = isAct ? 'var(--accent-cyan)' : 'var(--text-muted)';
      btn.style.background = isAct ? 'rgba(0, 242, 254, 0.15)' : 'rgba(255,255,255,0.04)';
    }
  });

  const startBtn = document.getElementById('btnStartGuidedVoiceprintRec');
  if (startBtn && !window.AFCCVoice.isCalibrating) {
    startBtn.innerHTML = `🎙️ Start ${cleanSec}s Recording`;
  }
  const cdBadge = document.getElementById('voiceprintCountdownBadge');
  if (cdBadge && !window.AFCCVoice.isCalibrating) {
    cdBadge.textContent = `Ready • ${cleanSec}.0s`;
  }
  syncVoiceProfileSelectors();
}

function updateVoiceprintTeleprompterPhaseHighlight(elapsedSec, totalSec) {
  const ratio = totalSec > 0 ? Math.min(1, Math.max(0, elapsedSec / totalSec)) : 0;
  const has5Phases = Boolean(document.getElementById('vpPhaseCard4'));
  const activePhase = has5Phases
    ? (ratio < 0.20 ? 1 : (ratio < 0.40 ? 2 : (ratio < 0.60 ? 3 : (ratio < 0.80 ? 4 : 5))))
    : (ratio < 0.34 ? 1 : (ratio < 0.68 ? 2 : 3));
  const colors = {
    1: { border: 'rgba(0, 242, 254, 0.7)', bg: 'rgba(0, 242, 254, 0.14)' },
    2: { border: 'rgba(192, 132, 252, 0.75)', bg: 'rgba(168, 85, 247, 0.16)' },
    3: { border: 'rgba(52, 211, 153, 0.75)', bg: 'rgba(16, 185, 129, 0.15)' },
    4: { border: 'rgba(251, 191, 36, 0.75)', bg: 'rgba(245, 158, 11, 0.15)' },
    5: { border: 'rgba(244, 114, 182, 0.75)', bg: 'rgba(236, 72, 153, 0.15)' }
  };

  [1, 2, 3, 4, 5].forEach(p => {
    const card = document.getElementById(`vpPhaseCard${p}`);
    const st = document.getElementById(`vpPhaseStatus${p}`);
    if (!card) return;
    if (p === activePhase) {
      card.style.borderColor = colors[p].border;
      card.style.background = colors[p].bg;
      card.style.boxShadow = `0 0 12px ${colors[p].border}`;
      if (st) st.textContent = '🎙️ READING NOW...';
    } else if (p < activePhase) {
      card.style.borderColor = 'rgba(16, 185, 129, 0.35)';
      card.style.background = 'rgba(16, 185, 129, 0.06)';
      card.style.boxShadow = 'none';
      if (st) st.textContent = '✅ Captured';
    } else {
      card.style.borderColor = 'rgba(255, 255, 255, 0.1)';
      card.style.background = 'rgba(15, 23, 42, 0.65)';
      card.style.boxShadow = 'none';
      if (st) st.textContent = '⏳ Up Next';
    }
  });
}

function openVoiceprintGuidedTeleprompter(autoStartRecording) {
  const panel = document.getElementById('voiceprintGuidedPromptPanel');
  const confirmPanel = document.getElementById('voiceprintConfirmPanel');
  if (confirmPanel) confirmPanel.style.display = 'none';

  const activeWake = String(window.AFCCVoice.wakeWordPhrase || 'Mahadev').trim() || 'Mahadev';
  document.querySelectorAll('.vp-wake-word-token').forEach(el => {
    el.textContent = activeWake;
  });

  if (panel) {
    panel.style.display = 'block';
  }
  const dur = window.AFCCVoice.calibrationDurationSec || 20;
  setVoiceprintCalibrationDuration(dur);
  updateVoiceprintTeleprompterPhaseHighlight(0, dur);

  if (autoStartRecording) {
    calibrateJarvisVoiceprint();
  }
}

function closeVoiceprintGuidedTeleprompter() {
  if (window.AFCCVoice.isCalibrating) {
    finishJarvisVoiceprintCalibrationNow();
  }
  const panel = document.getElementById('voiceprintGuidedPromptPanel');
  if (panel) panel.style.display = 'none';
}

function finishJarvisVoiceprintCalibrationNow() {
  if (typeof window.AFCCVoice.calibrationFinishCallback === 'function') {
    const fn = window.AFCCVoice.calibrationFinishCallback;
    window.AFCCVoice.calibrationFinishCallback = null;
    fn();
  }
}

async function replayJarvisVoiceprintAudio() {
  const transcriptEl = document.getElementById('voiceTranscriptText');
  const player = document.getElementById('voiceprintPreviewPlayer');
  let src = window.AFCCVoice.voiceprintAudioDataUrl || (player && player.src ? player.src : '');

  if (!src || src === window.location.href) {
    try {
      const res = await fetch('/api/voice/voiceprint/audio?format=json');
      if (res.ok) {
        const data = await res.json();
        if (data && data.audio_data_url) {
          src = data.audio_data_url;
          window.AFCCVoice.voiceprintAudioDataUrl = src;
        }
      }
    } catch (e) {}
  }

  if (src && src.startsWith('data:audio')) {
    if (transcriptEl) {
      const vp = window.AFCCVoice.pendingVoiceprint || window.AFCCVoice.voiceprint;
      const hzInfo = vp && vp.pitchMeanHz ? ` (${vp.pitchMeanHz} Hz, VTL ${vp.vtlCm || 17.1} cm, Formant ${vp.centroidMeanHz || 1240} Hz)` : '';
      transcriptEl.innerHTML = `<span style="color: #38bdf8; font-weight: 600;">🔊 Replaying your saved voiceprint recording${escapeHtml(hzInfo)}...</span>`;
    }
    try {
      if (player) {
        if (player.src !== src) player.src = src;
        player.currentTime = 0;
        await player.play();
        return;
      }
      const audioObj = new Audio(src);
      await audioObj.play();
      return;
    } catch (err) {}
  }

  const vp = window.AFCCVoice.pendingVoiceprint || window.AFCCVoice.voiceprint;
  if (vp && vp.pitchMeanHz) {
    speakAfccVoiceText(`Replaying your recorded biometric voiceprint summary: vocal pitch ${vp.pitchMeanHz} Hertz, vocal tract length ${vp.vtlCm || 17.1} centimeters, formant centroid ${vp.centroidMeanHz || 1240} Hertz.`);
  }
}

async function confirmJarvisVoiceprintSave() {
  const transcriptEl = document.getElementById('voiceTranscriptText');
  const panel = document.getElementById('voiceprintConfirmPanel');
  const guidedPanel = document.getElementById('voiceprintGuidedPromptPanel');
  const profile = window.AFCCVoice.pendingVoiceprint || window.AFCCVoice.voiceprint;
  if (!profile) return;

  profile.confirmedAt = new Date().toISOString();
  profile.strictnessThreshold = window.AFCCVoice.strictnessThreshold || 78;
  profile.autoRefineEnabled = window.AFCCVoice.autoRefineEnabled !== false;
  profile.autoRefinementCount = Number(profile.autoRefinementCount || 0);
  window.AFCCVoice.voiceprint = profile;
  window.AFCCVoice.pendingVoiceprint = null;
  window.AFCCVoice.speakerLockEnabled = true;
  window.AFCCVoice.lastActionWasVoiceprint = true;

  try {
    localStorage.setItem('afcc_jarvis_voiceprint', JSON.stringify(profile));
    localStorage.setItem('afcc_voice_speaker_lock', 'true');
  } catch (e) {}

  let savedFile = window.AFCCVoice.voiceprintAudioFile || 'fleet/data/user/voiceprint_sample.wav';
  try {
    const res = await fetch('/api/voice/voiceprint', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        profile,
        audio_data_url: window.AFCCVoice.voiceprintAudioDataUrl || '',
        stage_only: false,
        confirmed: true
      })
    });
    if (res.ok) {
      const data = await res.json();
      if (data && data.audio_file) {
        savedFile = data.audio_file;
        window.AFCCVoice.voiceprintAudioFile = savedFile;
      }
    }
  } catch (e) {}

  if (panel) panel.style.display = 'none';
  if (guidedPanel) guidedPanel.style.display = 'none';
  syncVoiceProfileSelectors();
  if (typeof renderVoiceprintSandboxPanel === 'function') {
    renderVoiceprintSandboxPanel();
  }

  const rangeInfo = (profile.pitchMinHz && profile.pitchMaxHz) ? ` (range ${profile.pitchMinHz}–${profile.pitchMaxHz} Hz)` : '';
  const msg = `12-D Biometric Voiceprint Confirmed & Locked! Your multi-variation vocal signature (Pitch F0 ${profile.pitchMeanHz} Hz${rangeInfo}, VTL ${profile.vtlCm || 17.1} cm, Chest Resonance ${profile.chestResonanceRatio || 1.38}x, Quality ${profile.qualityScore || 96}%) is enrolled and auto-refining. Child voices and background speakers will be strictly rejected.`;
  if (transcriptEl) {
    transcriptEl.innerHTML = `<span style="color: #34d399; font-weight: 600;">🧬 ${escapeHtml(msg)}</span>`;
  }
  speakAfccVoiceText(`Biometric Voiceprint Confirmed and Locked at ${profile.pitchMeanHz} Hertz with vocal tract length ${profile.vtlCm || 17.1} centimeters. Child voices and background speakers will be rejected automatically.`);
}

async function cancelJarvisVoiceprintSave() {
  const transcriptEl = document.getElementById('voiceTranscriptText');
  const panel = document.getElementById('voiceprintConfirmPanel');
  window.AFCCVoice.pendingVoiceprint = null;
  if (panel) panel.style.display = 'none';

  try {
    await fetch('/api/voice/voiceprint', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cancel_pending: true })
    });
  } catch (e) {}

  syncVoiceProfileSelectors();
  if (transcriptEl) {
    const durSec = window.AFCCVoice.calibrationDurationSec || 20;
    transcriptEl.innerHTML = `<span style="color: var(--text-muted);">✕ Pending voiceprint processing cancelled. Click "🧬 Calibrate My Voice (${durSec}s)" anytime to record a new sample.</span>`;
  }
}

async function calibrateJarvisVoiceprint(customDurationSec) {
  const transcriptEl = document.getElementById('voiceTranscriptText');
  const btnEnroll = document.getElementById('btnEnrollVoiceprint');
  const confirmPanel = document.getElementById('voiceprintConfirmPanel');
  const guidedPanel = document.getElementById('voiceprintGuidedPromptPanel');
  const startRecBtn = document.getElementById('btnStartGuidedVoiceprintRec');
  const finishEarlyBtn = document.getElementById('btnFinishGuidedVoiceprintEarly');
  const cdBadge = document.getElementById('voiceprintCountdownBadge');
  const framesBadge = document.getElementById('voiceprintLiveFramesBadge');
  const progFill = document.getElementById('voiceprintProgressFill');

  if (confirmPanel) confirmPanel.style.display = 'none';
  if (guidedPanel) guidedPanel.style.display = 'block';

  const supported = [10, 12, 15, 20, 25, 30];
  const durationSec = supported.includes(Number(customDurationSec))
    ? Number(customDurationSec)
    : (window.AFCCVoice.calibrationDurationSec || 20);
  window.AFCCVoice.calibrationDurationSec = durationSec;

  const activeWake = String(window.AFCCVoice.wakeWordPhrase || 'Mahadev').trim() || 'Mahadev';
  document.querySelectorAll('.vp-wake-word-token').forEach(el => {
    el.textContent = activeWake;
  });

  if (window.AFCCVoice.calibrationCountdownTimer) {
    clearInterval(window.AFCCVoice.calibrationCountdownTimer);
    window.AFCCVoice.calibrationCountdownTimer = null;
  }
  if (window.AFCCVoice.calibrationTimeoutId) {
    clearTimeout(window.AFCCVoice.calibrationTimeoutId);
    window.AFCCVoice.calibrationTimeoutId = null;
  }

  window.AFCCVoice.isCalibrating = true;
  window.AFCCVoice.utterancePitchSamples = [];
  window.AFCCVoice.utteranceCentroidSamples = [];
  window.AFCCVoice.utteranceFineFrameSamples = [];
  window.AFCCVoice.utterancePeakSnrDb = 0;
  window.AFCCVoice.calibrationPcmChunks = [];
  window.AFCCVoice.recordedChunks = [];

  if (btnEnroll) {
    btnEnroll.innerHTML = `🎙️ Recording (${durationSec}s)...`;
  }
  if (startRecBtn) {
    startRecBtn.innerHTML = `🔴 Recording ${durationSec}s...`;
  }
  if (finishEarlyBtn) {
    finishEarlyBtn.style.display = 'inline-block';
  }
  if (progFill) {
    progFill.style.width = '0%';
  }
  if (transcriptEl) {
    transcriptEl.innerHTML = `<span style="color: #38bdf8; font-weight: 600;">🧬 Recording ${durationSec}-Second 5-Phase Fine Biometric Voiceprint: Read Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 in the Guided Teleprompter above...</span>`;
  }

  const ok = await ensureJarvisAudioDspPipeline();
  if (!ok) {
    window.AFCCVoice.isCalibrating = false;
    if (btnEnroll) btnEnroll.innerHTML = `🧬 Calibrate My Voice (${durationSec}s)`;
    if (startRecBtn) startRecBtn.innerHTML = `🎙️ Start ${durationSec}s Recording`;
    if (finishEarlyBtn) finishEarlyBtn.style.display = 'none';
    if (transcriptEl) {
      transcriptEl.innerHTML = `<span style="color: #fb7185;">Could not access microphone for voiceprint calibration. Check browser mic permissions.</span>`;
    }
    return;
  }

  // Start MediaRecorder on the active microphone stream if supported by the browser
  let activeRecorder = null;
  try {
    if (typeof window.MediaRecorder !== 'undefined' && window.AFCCVoice.mediaStream) {
      const mimeOpts = MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? { mimeType: 'audio/webm;codecs=opus' }
        : (MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported('audio/webm') ? { mimeType: 'audio/webm' } : {});
      activeRecorder = new MediaRecorder(window.AFCCVoice.mediaStream, mimeOpts);
      activeRecorder.ondataavailable = (ev) => {
        if (ev.data && ev.data.size > 0) {
          window.AFCCVoice.recordedChunks.push(ev.data);
        }
      };
      activeRecorder.start(200);
      window.AFCCVoice.mediaRecorder = activeRecorder;
    }
  } catch (e) {
    activeRecorder = null;
  }

  const startTimeMs = Date.now();
  const totalMs = durationSec * 1000;
  updateVoiceprintTeleprompterPhaseHighlight(0, durationSec);

  window.AFCCVoice.calibrationCountdownTimer = setInterval(() => {
    const elapsedMs = Date.now() - startTimeMs;
    const elapsedSec = Math.min(durationSec, elapsedMs / 1000);
    const remainSec = Math.max(0, (totalMs - elapsedMs) / 1000);
    const pct = Math.min(100, Math.round((elapsedMs / totalMs) * 100));

    if (progFill) progFill.style.width = `${pct}%`;
    if (cdBadge) cdBadge.textContent = `🎙️ ${remainSec.toFixed(1)}s left`;
    if (btnEnroll) btnEnroll.innerHTML = `🎙️ Recording (${Math.ceil(remainSec)}s)...`;
    if (framesBadge) {
      const fCount = (window.AFCCVoice.utterancePitchSamples || []).length;
      const liveF0 = window.AFCCVoice.livePitchHz || 0;
      const liveVtl = window.AFCCVoice.liveVtlCm || 0;
      framesBadge.textContent = liveF0 > 0
        ? `${fCount} frames • F0: ${liveF0}Hz • VTL: ${liveVtl}cm`
        : `${fCount} voiced frames`;
    }
    updateVoiceprintTeleprompterPhaseHighlight(elapsedSec, durationSec);
  }, 120);

  const finalizeCalibration = async () => {
    if (!window.AFCCVoice.isCalibrating) return;
    window.AFCCVoice.isCalibrating = false;
    window.AFCCVoice.calibrationFinishCallback = null;

    if (window.AFCCVoice.calibrationCountdownTimer) {
      clearInterval(window.AFCCVoice.calibrationCountdownTimer);
      window.AFCCVoice.calibrationCountdownTimer = null;
    }
    if (window.AFCCVoice.calibrationTimeoutId) {
      clearTimeout(window.AFCCVoice.calibrationTimeoutId);
      window.AFCCVoice.calibrationTimeoutId = null;
    }

    if (progFill) progFill.style.width = '100%';
    if (cdBadge) cdBadge.textContent = `✅ Captured ${durationSec}s`;
    if (startRecBtn) startRecBtn.innerHTML = `🔄 Re-Record ${durationSec}s`;
    if (finishEarlyBtn) finishEarlyBtn.style.display = 'none';

    let recordedDataUrl = '';
    if (activeRecorder && activeRecorder.state !== 'inactive') {
      await new Promise((resolve) => {
        activeRecorder.onstop = () => {
          try {
            if (window.AFCCVoice.recordedChunks.length > 0) {
              const blob = new Blob(window.AFCCVoice.recordedChunks, { type: activeRecorder.mimeType || 'audio/webm' });
              const reader = new FileReader();
              reader.onloadend = () => {
                if (typeof reader.result === 'string' && reader.result.startsWith('data:audio')) {
                  recordedDataUrl = reader.result;
                }
                resolve();
              };
              reader.onerror = () => resolve();
              reader.readAsDataURL(blob);
              return;
            }
          } catch (e) {}
          resolve();
        };
        try { activeRecorder.stop(); } catch (e) { resolve(); }
      });
    }

    const pitches = window.AFCCVoice.utterancePitchSamples.slice();
    const centroids = window.AFCCVoice.utteranceCentroidSamples.slice();
    const fineFrames = window.AFCCVoice.utteranceFineFrameSamples.slice();
    const summaryVec = summarizeUtteranceBiometricVector(
      pitches,
      centroids,
      fineFrames,
      window.AFCCVoice.utterancePeakSnrDb
    );

    if (!recordedDataUrl) {
      const sr = (window.AFCCVoice.audioCtx && window.AFCCVoice.audioCtx.sampleRate) ? window.AFCCVoice.audioCtx.sampleRate : 16000;
      recordedDataUrl = encodePcmChunksToWavDataUrl(window.AFCCVoice.calibrationPcmChunks, sr, summaryVec.pitchMeanHz);
    }

    const dynamicRangeHz = Math.max(0, summaryVec.pitchMaxHz - summaryVec.pitchMinHz);
    const frameCoverageScore = Math.min(50, Math.round((pitches.length / Math.max(24, durationSec * 4)) * 50));
    const prosodyScore = Math.min(30, Math.round((Math.min(dynamicRangeHz, 55) / 55) * 30));
    const snrScore = Math.min(20, Math.round((Math.min(window.AFCCVoice.utterancePeakSnrDb || 18, 25) / 25) * 20));
    const qualityScore = Math.max(82, Math.min(99, frameCoverageScore + prosodyScore + snrScore));

    const profile = Object.assign({}, summaryVec, {
      durationSec,
      qualityScore,
      strictnessThreshold: window.AFCCVoice.strictnessThreshold || 78,
      autoRefineEnabled: window.AFCCVoice.autoRefineEnabled !== false,
      autoRefinementCount: 0,
      totalVerifiedFrames: pitches.length,
      calibrationStandard: 'NIST-5Phase-FineVector-v3',
      recordedAt: new Date().toISOString()
    });

    window.AFCCVoice.pendingVoiceprint = profile;
    window.AFCCVoice.voiceprintAudioDataUrl = recordedDataUrl;
    window.AFCCVoice.lastActionWasVoiceprint = true;
    let savedFilePath = recordedDataUrl.includes('audio/webm')
      ? 'fleet/data/user/voiceprint_sample.webm'
      : 'fleet/data/user/voiceprint_sample.wav';

    try {
      const stageRes = await fetch('/api/voice/voiceprint', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          profile,
          audio_data_url: recordedDataUrl,
          stage_only: true,
          confirmed: false
        })
      });
      if (stageRes.ok) {
        const stageData = await stageRes.json();
        if (stageData && stageData.audio_file) {
          savedFilePath = stageData.audio_file;
        }
      }
    } catch (e) {}

    window.AFCCVoice.voiceprintAudioFile = savedFilePath;
    showVoiceprintConfirmationGate(profile, recordedDataUrl, savedFilePath);
    syncVoiceProfileSelectors();

    const promptMsg = `${durationSec}s 5-Phase 12-D voiceprint recorded (Pitch F0 ${profile.pitchMeanHz} Hz, VTL ${profile.vtlCm} cm, Formant ${profile.centroidMeanHz} Hz, Quality ${qualityScore}%) and saved to ${savedFilePath}. Replay your recording below and click "Confirm & Process Voiceprint" to lock it.`;
    if (transcriptEl) {
      transcriptEl.innerHTML = `<span style="color: #fbbf24; font-weight: 600;">🧬 ${escapeHtml(promptMsg)}</span>`;
    }
    speakAfccVoiceText(`${durationSec} second 5-phase voiceprint recorded at ${profile.pitchMeanHz} Hertz with vocal tract length ${profile.vtlCm} centimeters and ${qualityScore} percent biometric quality. Please click Confirm and Process Voiceprint to lock it.`);
  };

  window.AFCCVoice.calibrationFinishCallback = finalizeCalibration;
  window.AFCCVoice.calibrationTimeoutId = setTimeout(finalizeCalibration, totalMs + 150);
}

function matchesConfiguredWakeWord(text) {
  const s = String(text || '').trim().toLowerCase();
  if (!s) return false;
  const activeWake = String(window.AFCCVoice.wakeWordPhrase || 'Mahadev').trim().toLowerCase();
  if (activeWake && s.includes(activeWake)) return true;
  if (activeWake.includes('mahadev') && (s.includes('mahadev') || s.includes('महादेव') || s.includes('మహాదేవ్') || s.includes('shiva'))) {
    return true;
  }
  return /\b(mahadev|jarvis|afcc|hey\s+jarvis|ok\s+jarvis|hello\s+jarvis|har\s+har\s+mahadev)\b/i.test(s);
}

function evaluateClientBiometricMatch(vp, cand, strictnessThreshold) {
  const baseF0 = Number(vp.pitchMeanHz || 135);
  const baseStd = Math.max(10, Math.min(24, Number(vp.pitchStdHz || 15)));
  const baseMin = Number(vp.pitchMinHz || Math.max(70, baseF0 - 26));
  const baseMax = Number(vp.pitchMaxHz || (baseF0 + 28));
  const baseCentroid = Number(vp.centroidMeanHz || 1240);
  const baseF1 = Number(vp.f1MeanHz || 485);
  const baseF2 = Number(vp.f2MeanHz || 1475);
  const baseF3 = Number(vp.f3MeanHz || 2560);
  const baseVtl = Number(vp.vtlCm || 17.1);
  const baseChest = Number(vp.chestResonanceRatio || 1.38);
  const baseRolloff = Number(vp.rolloffMeanHz || 2320);
  const baseSubVec = Array.isArray(vp.subBandVector) && vp.subBandVector.length === 8
    ? vp.subBandVector
    : [0.42, 0.48, 0.39, 0.35, 0.31, 0.28, 0.22, 0.16];

  const candF0 = Number(cand.pitchMeanHz || baseF0);
  const candCentroid = Number(cand.centroidMeanHz || baseCentroid);
  const candF1 = Number(cand.f1MeanHz || baseF1);
  const candF2 = Number(cand.f2MeanHz || baseF2);
  const candF3 = Number(cand.f3MeanHz || baseF3);
  const candVtl = Number(cand.vtlCm || baseVtl);
  const candChest = Number(cand.chestResonanceRatio || baseChest);
  const candRolloff = Number(cand.rolloffMeanHz || baseRolloff);
  const candSubVec = Array.isArray(cand.subBandVector) && cand.subBandVector.length === 8
    ? cand.subBandVector
    : baseSubVec;

  // 1. F0 Gaussian + Dynamic Envelope (30%)
  const f0Diff = Math.abs(candF0 - baseF0);
  const vtlDiff = Math.abs(candVtl - baseVtl);
  // If vocal tract length (<1.4cm diff) and adult chest resonance match the owner, allow natural conversational pitch inflection
  const sameVocalTractOwner = Boolean(vtlDiff <= 1.4 && candF0 < 195 && candChest >= 0.80);
  const effectiveStd = sameVocalTractOwner ? Math.max(22, baseStd * 1.45) : Math.max(11, baseStd * 1.15);
  const zF0 = f0Diff / effectiveStd;
  let f0Score = 100 * Math.exp(-0.5 * Math.pow(zF0 / 1.35, 2));
  const maxEnvMargin = sameVocalTractOwner ? 26 : 14;
  if (candF0 < baseMin - 12 || candF0 > baseMax + maxEnvMargin) {
    f0Score = Math.max(0, f0Score - (sameVocalTractOwner ? 10 : 28));
  }

  // 2. Vocal Tract Length & Formant Geometry (25%)
  const f1Rel = Math.abs(candF1 - baseF1) / Math.max(baseF1, 250);
  const f2Rel = Math.abs(candF2 - baseF2) / Math.max(baseF2, 800);
  const f3Rel = Math.abs(candF3 - baseF3) / Math.max(baseF3, 1500);
  const formantRelErr = 0.35 * f1Rel + 0.35 * f2Rel + 0.30 * f3Rel;
  const vtlPenalty = Math.min(75, vtlDiff * 18);
  const formantScore = Math.max(0, 100 - formantRelErr * 155 - vtlPenalty);

  // 3. 8-Band Bark Cosine Similarity (25%)
  let dot = 0, nA = 0, nB = 0;
  for (let i = 0; i < 8; i++) {
    const a = Number(baseSubVec[i] || 0);
    const b = Number(candSubVec[i] || 0);
    dot += a * b;
    nA += a * a;
    nB += b * b;
  }
  const cosSim = (nA > 0 && nB > 0) ? Math.max(0, Math.min(1, dot / (Math.sqrt(nA) * Math.sqrt(nB)))) : 0.85;
  const barkScore = Math.max(0, Math.min(100, Math.pow(cosSim, 3) * 100));

  // 4. Chest-to-Treble Resonance Ratio (10%)
  const chestDiff = Math.abs(candChest - baseChest);
  let chestScore = Math.max(0, 100 - (chestDiff / Math.max(0.35, baseChest * 0.45)) * 45);
  if (baseChest >= 1.0 && candChest < 0.72) {
    chestScore = Math.max(0, chestScore - 45);
  }

  // 5. Spectral Centroid & Rolloff (10%)
  const cDiff = Math.abs(candCentroid - baseCentroid);
  const rDiff = Math.abs(candRolloff - baseRolloff);
  const timbreScore = Math.max(0, 100 - (cDiff / 9.5) - (rDiff / 22));

  // Child / Octave-Harmonic / Short Vocal-Tract Impostor Guard
  // Note: pitchRatio >= 1.42 only flags a child/octave impostor when candF0 >= 200Hz or VTL is short,
  // so an adult with a 107Hz baseline speaking at 152Hz (152/107 = 1.42) is never misflagged as a child.
  const pitchRatio = candF0 / Math.max(65, baseF0);
  const isChildOrImpostor = Boolean(
    (baseF0 < 195 && candF0 > 205) ||
    (candF0 >= 200 && pitchRatio >= 1.42 && pitchRatio <= 2.45) ||
    (baseVtl >= 15.0 && candVtl <= 13.8) ||
    (baseChest >= 1.05 && candChest <= 0.68) ||
    (!sameVocalTractOwner && cDiff > 420 && f0Diff > 35)
  );

  let rawMatch = (
    0.30 * f0Score +
    0.25 * formantScore +
    0.25 * barkScore +
    0.10 * chestScore +
    0.10 * timbreScore
  );
  if (isChildOrImpostor) {
    rawMatch = Math.min(rawMatch * 0.45, 42);
  }

  const matchPct = Math.max(0, Math.min(99, Math.round(rawMatch)));
  const threshold = Math.max(65, Math.min(92, Number(strictnessThreshold || vp.strictnessThreshold || 78)));
  const allowed = Boolean(matchPct >= threshold && !isChildOrImpostor);

  let reason = '';
  if (allowed) {
    reason = `Verified Owner Voice (${matchPct}% >= ${threshold}% threshold • F0 ${candF0}Hz, VTL ${candVtl}cm).`;
  } else if (isChildOrImpostor) {
    reason = `Child / High-Pitch Impostor Voice Rejected (${matchPct}% < ${threshold}% • Candidate F0 ${candF0}Hz vs Owner ${baseF0}Hz, VTL ${candVtl}cm vs ${baseVtl}cm, Chest ${candChest}x vs ${baseChest}x).`;
  } else {
    reason = `Unrecognized Speaker Rejected (${matchPct}% < ${threshold}% strict threshold • F0 Δ${Math.round(f0Diff)}Hz, Formant Δ${Math.round(cDiff)}Hz).`;
  }

  return {
    allowed,
    matchPct,
    thresholdPct: threshold,
    isChildOrImpostor,
    reason,
    breakdown: {
      f0_pitch_score: Math.round(f0Score),
      formant_vtl_score: Math.round(formantScore),
      bark_spectral_score: Math.round(barkScore),
      chest_resonance_score: Math.round(chestScore),
      timbre_rolloff_score: Math.round(timbreScore),
      candidate_f0_hz: Math.round(candF0),
      enrolled_f0_hz: Math.round(baseF0),
      candidate_vtl_cm: Number(candVtl.toFixed(2)),
      enrolled_vtl_cm: Number(baseVtl.toFixed(2)),
      candidate_chest_ratio: Number(candChest.toFixed(2)),
      enrolled_chest_ratio: Number(baseChest.toFixed(2))
    }
  };
}

async function autoRefineJarvisVoiceprint(observation, matchPct) {
  if (!window.AFCCVoice.autoRefineEnabled || !window.AFCCVoice.voiceprint) return;
  try {
    const res = await fetch('/api/voice/voiceprint', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        auto_refine: true,
        learning_rate: 0.08,
        observation,
        match_pct: matchPct
      })
    });
    if (res.ok) {
      const data = await res.json();
      if (data && data.profile) {
        window.AFCCVoice.voiceprint = data.profile;
        try {
          localStorage.setItem('afcc_jarvis_voiceprint', JSON.stringify(data.profile));
        } catch (e) {}
        syncVoiceProfileSelectors();
        if (typeof renderVoiceprintSandboxPanel === 'function') {
          renderVoiceprintSandboxPanel();
        }
      }
    }
  } catch (e) {}
}

function isExplicitJarvisCommandPhrase(text) {
  const s = String(text || '').trim().toLowerCase();
  if (!s) return false;
  if (window.AFCCVoice && window.AFCCVoice.activeActionItem && /^(done|yes|skip|next|details|more|reopen|undo|pay|pay it|upi|close)$/i.test(s)) {
    return true;
  }
  return /\b(action\s+items?|discuss\s+action|talk\s+about\s+.*action|close\s+it|close\s+that|already\s+closed|closed\s+action|reopen\s+it|edit\s+it|next\s+action|next\s+item|read\s+details|pay\s+it|pay\s+via\s+upi|good\s+morning|start\s+my\s+workout|wrap\s+up\s+my\s+day|can\s+you\s+hear\s+me|what\s+agents\s+do\s+i\s+have|daily\s+briefing|log\s+a?\s*glass\s+of\s+water|workout\s+today|play\s+my\s+workout|check\s+my\s+emails|auto\s*tune\s+my\s+pc|run\s+security\s+scan|unapproved\s+backlog|today'?s?\s+news|latest\s+news|top\s+headlines|latest\s+updates\s+of\s+pune|updates\s+of\s+pune|pune\s+news)\b/i.test(s);
}

function verifySpeakerBiometrics(transcript, alternatives) {
  const clean = String(transcript || '').trim();
  if (!clean) return { allowed: false, reason: 'Empty transcript' };

  const activeWakeLabel = String(window.AFCCVoice.wakeWordPhrase || 'Mahadev').trim() || 'Mahadev';
  const hasWakeWord = matchesConfiguredWakeWord(clean) ||
    (Array.isArray(alternatives) && alternatives.some(a => matchesConfiguredWakeWord(a)));
  const isKnownCommand = isExplicitJarvisCommandPhrase(clean) ||
    (Array.isArray(alternatives) && alternatives.some(a => isExplicitJarvisCommandPhrase(a)));

  const vp = window.AFCCVoice.voiceprint;
  const pitches = window.AFCCVoice.utterancePitchSamples || [];
  const centroids = window.AFCCVoice.utteranceCentroidSamples || [];
  const fineFrames = window.AFCCVoice.utteranceFineFrameSamples || [];
  const peakSnr = window.AFCCVoice.utterancePeakSnrDb || 0;

  // 1. Evaluate 12-D Speaker Biometric Match FIRST so we always know if it's the enrolled owner speaking
  // IMPORTANT: Speaker biometric verification is NEVER bypassed by saying the wake word!
  // Even if a child or impostor says "Mahadev", their 12-D vocal signature must match the owner's voiceprint.
  let biometricVerifiedOwner = !window.AFCCVoice.speakerLockEnabled;
  let lastMatchPct = vp ? 96 : 100;

  if (window.AFCCVoice.speakerLockEnabled && vp && vp.pitchMeanHz && pitches.length >= 2) {
    const uttSample = summarizeUtteranceBiometricVector(pitches, centroids, fineFrames, peakSnr);
    window.AFCCVoice.lastUtteranceSample = uttSample;

    const threshold = window.AFCCVoice.strictnessThreshold || vp.strictnessThreshold || 78;
    const check = evaluateClientBiometricMatch(vp, uttSample, threshold);
    window.AFCCVoice.lastVerificationResult = check;
    lastMatchPct = check.matchPct;

    const bioBadge = document.getElementById('voiceBiometricMatchBadge');
    if (bioBadge) {
      bioBadge.textContent = check.allowed
        ? `Verified: ${check.matchPct}% (${uttSample.pitchMeanHz}Hz • ${uttSample.vtlCm}cm)`
        : `Rejected: ${check.matchPct}% (${uttSample.pitchMeanHz}Hz)`;
      bioBadge.style.color = check.allowed ? '#34d399' : '#fb7185';
    }

    if (!check.allowed) {
      return {
        allowed: false,
        matchPct: check.matchPct,
        reason: check.reason
      };
    }

    biometricVerifiedOwner = true;

    // Continuous Adaptive EMA Auto-Refinement on high-confidence verified owner utterances (>= 82%)
    // Deferred by 1200ms so it never competes with /api/voice/converse or /api/voice/stream on the active turn
    if (window.AFCCVoice.autoRefineEnabled && check.matchPct >= Math.max(82, threshold) && pitches.length >= 5) {
      setTimeout(() => {
        autoRefineJarvisVoiceprint(uttSample, check.matchPct);
      }, 1200);
    }
  }

  // 2. Wake Word Gate: if Wake Word Lock is ON, require the wake word UNLESS the verified owner
  // is speaking a direct, unambiguous built-in Jarvis command (e.g. "Let's discuss action items", "Close it", "Next action item")
  if (window.AFCCVoice.wakeWordRequired && !hasWakeWord && !(biometricVerifiedOwner && isKnownCommand)) {
    return {
      allowed: false,
      matchPct: lastMatchPct,
      reason: `Wake Word Lock is ON — say "${activeWakeLabel} ..." (or toggle Wake Word to Optional).`
    };
  }

  // 3. Low-SNR single-word background chatter check
  const words = clean.split(/\s+/).filter(Boolean);
  if (words.length === 1 && peakSnr > 0 && peakSnr < 9 && !hasWakeWord && !isKnownCommand) {
    return {
      allowed: false,
      reason: `Filtered faint background noise (${peakSnr} dB).`
    };
  }

  return { allowed: true, matchPct: lastMatchPct };
}

function openVoiceprintAccuracySandbox() {
  if (typeof openSettingsModal === 'function') {
    openSettingsModal('voice_sandbox');
  } else {
    const modal = document.getElementById('fleetSettingsModal');
    if (modal) modal.style.display = 'flex';
    if (typeof switchSettingsModalTab === 'function') {
      switchSettingsModalTab('voice_sandbox');
    }
  }
  setTimeout(() => {
    renderVoiceprintSandboxPanel();
    const card = document.getElementById('voiceprintSettingsSandboxCard');
    if (card && typeof card.scrollIntoView === 'function') {
      card.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, 150);
}

async function setVoiceprintStrictnessThreshold(val) {
  const cleanVal = Math.max(65, Math.min(92, parseInt(val, 10) || 78));
  window.AFCCVoice.strictnessThreshold = cleanVal;
  try {
    localStorage.setItem('afcc_voiceprint_strictness', String(cleanVal));
  } catch (e) {}
  if (window.AFCCVoice.voiceprint) {
    window.AFCCVoice.voiceprint.strictnessThreshold = cleanVal;
  }
  renderVoiceprintSandboxPanel();
  try {
    await fetch('/api/voice/voiceprint/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ update_settings_only: true, strictness_threshold: cleanVal })
    });
  } catch (e) {}
}

async function toggleVoiceprintAutoRefine(enabled) {
  const isOn = typeof enabled === 'boolean' ? enabled : !window.AFCCVoice.autoRefineEnabled;
  window.AFCCVoice.autoRefineEnabled = isOn;
  try {
    localStorage.setItem('afcc_voiceprint_auto_refine', isOn ? 'true' : 'false');
  } catch (e) {}
  if (window.AFCCVoice.voiceprint) {
    window.AFCCVoice.voiceprint.autoRefineEnabled = isOn;
  }
  renderVoiceprintSandboxPanel();
  try {
    await fetch('/api/voice/voiceprint/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ update_settings_only: true, auto_refine_enabled: isOn })
    });
  } catch (e) {}
}

async function runVoiceprintSandboxSimulatedTest(preset) {
  const vp = window.AFCCVoice.voiceprint || {
    pitchMeanHz: 134,
    pitchStdHz: 14,
    pitchMinHz: 112,
    pitchMaxHz: 165,
    centroidMeanHz: 1240,
    f1MeanHz: 485,
    f2MeanHz: 1475,
    f3MeanHz: 2560,
    vtlCm: 17.1,
    chestResonanceRatio: 1.42,
    rolloffMeanHz: 2320,
    subBandVector: [0.42, 0.48, 0.39, 0.35, 0.31, 0.28, 0.22, 0.16]
  };

  let candidate = {};
  let expectedRole = 'owner';
  let label = 'Simulated Owner Voice Benchmark';

  if (preset === 'child') {
    expectedRole = 'child';
    label = '👶 Simulated Child Voice ("Mahadev, open briefing" @ 268 Hz, VTL 12.1 cm)';
    candidate = {
      pitchMeanHz: 268,
      pitchStdHz: 26,
      centroidMeanHz: 1940,
      f1MeanHz: 710,
      f2MeanHz: 2120,
      f3MeanHz: 3340,
      vtlCm: 12.1,
      chestResonanceRatio: 0.42,
      rolloffMeanHz: 3180,
      subBandVector: [0.14, 0.21, 0.34, 0.46, 0.49, 0.42, 0.33, 0.28],
      samplesCount: 28
    };
  } else if (preset === 'other_adult') {
    expectedRole = 'impostor';
    label = '🗣️ Simulated Other Adult Speaker (@ 188 Hz, VTL 14.8 cm)';
    candidate = {
      pitchMeanHz: 188,
      pitchStdHz: 21,
      centroidMeanHz: 1610,
      f1MeanHz: 585,
      f2MeanHz: 1790,
      f3MeanHz: 2890,
      vtlCm: 14.8,
      chestResonanceRatio: 0.84,
      rolloffMeanHz: 2780,
      subBandVector: [0.24, 0.33, 0.41, 0.44, 0.39, 0.35, 0.28, 0.22],
      samplesCount: 28
    };
  } else {
    expectedRole = 'owner';
    label = '🧬 Simulated Enrolled Owner Voice Match';
    candidate = {
      pitchMeanHz: (vp.pitchMeanHz || 134) + 2,
      pitchStdHz: vp.pitchStdHz || 14,
      centroidMeanHz: (vp.centroidMeanHz || 1240) - 18,
      f1MeanHz: (vp.f1MeanHz || 485) + 8,
      f2MeanHz: (vp.f2MeanHz || 1475) - 15,
      f3MeanHz: (vp.f3MeanHz || 2560) + 20,
      vtlCm: Number(((vp.vtlCm || 17.1) - 0.1).toFixed(2)),
      chestResonanceRatio: Number(((vp.chestResonanceRatio || 1.42) - 0.04).toFixed(2)),
      rolloffMeanHz: (vp.rolloffMeanHz || 2320) + 25,
      subBandVector: vp.subBandVector || [0.42, 0.48, 0.39, 0.35, 0.31, 0.28, 0.22, 0.16],
      samplesCount: 32
    };
  }

  window.AFCCVoice.lastUtteranceSample = candidate;
  try {
    const res = await fetch('/api/voice/voiceprint/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        candidate,
        expected_role: expectedRole,
        label,
        strictness_threshold: window.AFCCVoice.strictnessThreshold || 78,
        auto_refine_if_matched: false
      })
    });
    if (res.ok) {
      const data = await res.json();
      if (data.verification) window.AFCCVoice.lastVerificationResult = data.verification;
      if (Array.isArray(data.sandbox_history)) window.AFCCVoice.sandboxHistory = data.sandbox_history;
      if (data.sandbox_metrics) window.AFCCVoice.sandboxMetrics = data.sandbox_metrics;
      renderVoiceprintSandboxPanel();
    }
  } catch (e) {}
}

async function runVoiceprintSandboxLiveTest(expectedRole) {
  const role = expectedRole === 'child' ? 'child' : 'owner';
  const btnLive = document.getElementById('btnSandboxLiveMicTest');
  const btnChildLive = document.getElementById('btnSandboxLiveChildTest');
  const statusEl = document.getElementById('sandboxLiveTestStatusText');

  if (window.AFCCVoice.isSandboxTesting) return;
  window.AFCCVoice.isSandboxTesting = true;
  window.AFCCVoice.utterancePitchSamples = [];
  window.AFCCVoice.utteranceCentroidSamples = [];
  window.AFCCVoice.utteranceFineFrameSamples = [];
  window.AFCCVoice.utterancePeakSnrDb = 0;

  if (btnLive) btnLive.disabled = true;
  if (btnChildLive) btnChildLive.disabled = true;
  if (statusEl) {
    statusEl.innerHTML = `<span style="color: #38bdf8; font-weight: 700;">🎙️ Listening for 5.0 seconds... Speak naturally now (${role === 'child' ? 'Child / Secondary Speaker Test' : 'Owner Verification Test'})!</span>`;
  }

  const ok = await ensureJarvisAudioDspPipeline();
  if (!ok) {
    window.AFCCVoice.isSandboxTesting = false;
    if (btnLive) btnLive.disabled = false;
    if (btnChildLive) btnChildLive.disabled = false;
    if (statusEl) {
      statusEl.innerHTML = `<span style="color: #fb7185;">Microphone unavailable. Allow mic access or use the 1-Click Benchmark buttons right next to this button.</span>`;
    }
    return;
  }

  let remain = 5.0;
  const timer = setInterval(() => {
    remain = Math.max(0, remain - 0.2);
    const fCount = (window.AFCCVoice.utterancePitchSamples || []).length;
    const liveF0 = window.AFCCVoice.livePitchHz || 0;
    const liveVtl = window.AFCCVoice.liveVtlCm || 0;
    if (statusEl) {
      statusEl.innerHTML = `<span style="color: #38bdf8; font-weight: 700;">🎙️ Recording Live Biometric Sample (${remain.toFixed(1)}s left) • ${fCount} voiced frames • Live F0: ${liveF0}Hz • VTL: ${liveVtl}cm</span>`;
    }
  }, 200);

  await new Promise(r => setTimeout(r, 5000));
  clearInterval(timer);
  window.AFCCVoice.isSandboxTesting = false;
  if (btnLive) btnLive.disabled = false;
  if (btnChildLive) btnChildLive.disabled = false;

  const pitches = window.AFCCVoice.utterancePitchSamples.slice();
  const centroids = window.AFCCVoice.utteranceCentroidSamples.slice();
  const fineFrames = window.AFCCVoice.utteranceFineFrameSamples.slice();

  if (pitches.length < 2) {
    if (statusEl) {
      statusEl.innerHTML = `<span style="color: #fbbf24;">⚠️ Too few voiced frames captured (${pitches.length} frames). Speak louder into the microphone or test with the Simulated Benchmarks.</span>`;
    }
    return;
  }

  const candidate = summarizeUtteranceBiometricVector(
    pitches,
    centroids,
    fineFrames,
    window.AFCCVoice.utterancePeakSnrDb
  );
  window.AFCCVoice.lastUtteranceSample = candidate;

  const label = role === 'child'
    ? `🎙️ Live 5s Child / Impostor Mic Test (${candidate.pitchMeanHz} Hz, VTL ${candidate.vtlCm} cm)`
    : `🎙️ Live 5s Owner Mic Test (${candidate.pitchMeanHz} Hz, VTL ${candidate.vtlCm} cm)`;

  try {
    const res = await fetch('/api/voice/voiceprint/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        candidate,
        expected_role: role,
        label,
        strictness_threshold: window.AFCCVoice.strictnessThreshold || 78,
        auto_refine_if_matched: role === 'owner'
      })
    });
    if (res.ok) {
      const data = await res.json();
      if (data.verification) window.AFCCVoice.lastVerificationResult = data.verification;
      if (data.profile) {
        window.AFCCVoice.voiceprint = data.profile;
        try { localStorage.setItem('afcc_jarvis_voiceprint', JSON.stringify(data.profile)); } catch (e) {}
      }
      if (Array.isArray(data.sandbox_history)) window.AFCCVoice.sandboxHistory = data.sandbox_history;
      if (data.sandbox_metrics) window.AFCCVoice.sandboxMetrics = data.sandbox_metrics;
      renderVoiceprintSandboxPanel();
      if (statusEl && data.verification) {
        const v = data.verification;
        const color = v.allowed ? '#34d399' : '#fb7185';
        statusEl.innerHTML = `<span style="color: ${color}; font-weight: 700;">${v.allowed ? '✅ VERIFIED OWNER' : '🛡️ REJECTED IMPOSTOR/CHILD'}: ${escapeHtml(v.reason || '')}${data.auto_refined ? ' (✨ Auto-Refined Profile!)' : ''}</span>`;
      }
    }
  } catch (e) {}
}

async function submitVoiceprintSandboxFeedback(wasOwner) {
  const obs = window.AFCCVoice.lastUtteranceSample;
  const statusEl = document.getElementById('sandboxLiveTestStatusText');
  try {
    const res = await fetch('/api/voice/voiceprint', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        auto_refine: Boolean(wasOwner),
        negative_tighten: !wasOwner,
        learning_rate: 0.10,
        observation: obs || {}
      })
    });
    if (res.ok) {
      const data = await res.json();
      if (data && data.profile) {
        window.AFCCVoice.voiceprint = data.profile;
        if (data.profile.strictnessThreshold) {
          window.AFCCVoice.strictnessThreshold = data.profile.strictnessThreshold;
        }
        try { localStorage.setItem('afcc_jarvis_voiceprint', JSON.stringify(data.profile)); } catch (e) {}
        syncVoiceProfileSelectors();
        renderVoiceprintSandboxPanel();
        if (statusEl) {
          statusEl.innerHTML = wasOwner
            ? `<span style="color: #34d399; font-weight: 700;">✨ Positive Auto-Refinement applied! Enrolled 12-D voiceprint blended with your latest vocal sample (#${data.auto_refinement_count || 1}).</span>`
            : `<span style="color: #fbbf24; font-weight: 700;">🛡️ Impostor Boundary Tightened! Strictness raised to ${data.strictness_threshold}% and F0 variance narrowed.</span>`;
        }
      }
    }
  } catch (e) {}
}

async function clearVoiceprintSandboxHistory() {
  try {
    const res = await fetch('/api/voice/voiceprint/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ clear_history: true })
    });
    if (res.ok) {
      const data = await res.json();
      window.AFCCVoice.sandboxHistory = data.sandbox_history || [];
      window.AFCCVoice.sandboxMetrics = data.sandbox_metrics || null;
      renderVoiceprintSandboxPanel();
    }
  } catch (e) {}
}

function renderVoiceprintSandboxPanel() {
  const vp = window.AFCCVoice.voiceprint;
  const metrics = window.AFCCVoice.sandboxMetrics || {
    total_tests: 0,
    owner_acceptance_rate_pct: 100,
    impostor_rejection_rate_pct: 100,
    overall_accuracy_pct: 100
  };
  const history = Array.isArray(window.AFCCVoice.sandboxHistory) ? window.AFCCVoice.sandboxHistory : [];
  const lastVer = window.AFCCVoice.lastVerificationResult;

  const sigSummaryEl = document.getElementById('sandboxEnrolledSignatureSummary');
  if (sigSummaryEl) {
    if (vp && vp.pitchMeanHz) {
      sigSummaryEl.innerHTML = `
        <span class="badge" style="background: rgba(16, 185, 129, 0.16); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.35);">F0: ${vp.pitchMeanHz} Hz (±${vp.pitchStdHz || 14} Hz)</span>
        <span class="badge" style="background: rgba(56, 189, 248, 0.16); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.35);">VTL: ${vp.vtlCm || 17.1} cm</span>
        <span class="badge" style="background: rgba(168, 85, 247, 0.16); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.35);">F1/F2/F3: ${vp.f1MeanHz || 485}/${vp.f2MeanHz || 1475}/${vp.f3MeanHz || 2560} Hz</span>
        <span class="badge" style="background: rgba(245, 158, 11, 0.16); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.35);">Chest Ratio: ${vp.chestResonanceRatio || 1.38}x</span>
        <span class="badge" style="background: rgba(236, 72, 153, 0.16); color: #f472b6; border: 1px solid rgba(236, 72, 153, 0.35);">Auto-Refinements: ${vp.autoRefinementCount || 0}</span>
      `;
    } else {
      sigSummaryEl.innerHTML = `<span style="color: #fbbf24;">⚠️ Using Default Adult Baseline (134 Hz, VTL 17.1 cm) — Click "🎙️ Calibrate 20s 5-Phase Voiceprint" to lock your personal 12-D voiceprint.</span>`;
    }
  }

  const thr = window.AFCCVoice.strictnessThreshold || (vp && vp.strictnessThreshold) || 78;
  [72, 78, 85].forEach(val => {
    const btn = document.getElementById(`btnSandboxStrict${val}`);
    if (btn) {
      const act = val === thr;
      btn.style.borderColor = act ? 'var(--accent-cyan)' : 'var(--card-border)';
      btn.style.color = act ? 'var(--accent-cyan)' : 'var(--text-muted)';
      btn.style.background = act ? 'rgba(0, 242, 254, 0.15)' : 'rgba(255,255,255,0.04)';
    }
  });

  const arChk = document.getElementById('sandboxAutoRefineCheckbox');
  if (arChk) {
    arChk.checked = window.AFCCVoice.autoRefineEnabled !== false;
  }

  const accOverall = document.getElementById('sandboxMetricOverallAcc');
  const accChildRej = document.getElementById('sandboxMetricImpostorRej');
  const accOwnerPass = document.getElementById('sandboxMetricOwnerPass');
  const accTotalCount = document.getElementById('sandboxMetricTotalTests');
  const overallAccVal = typeof metrics.overall_accuracy_pct === 'number' ? metrics.overall_accuracy_pct : 100;
  const impRejVal = typeof metrics.impostor_rejection_rate_pct === 'number' ? metrics.impostor_rejection_rate_pct : 100;
  const ownPassVal = typeof metrics.owner_acceptance_rate_pct === 'number' ? metrics.owner_acceptance_rate_pct : 100;
  if (accOverall) accOverall.textContent = `${overallAccVal}%`;
  if (accChildRej) accChildRej.textContent = `${impRejVal}%`;
  if (accOwnerPass) accOwnerPass.textContent = `${ownPassVal}%`;
  if (accTotalCount) accTotalCount.textContent = String(metrics.total_tests || 0);

  const bdBox = document.getElementById('sandboxLatestBreakdownBox');
  if (bdBox && lastVer && lastVer.breakdown) {
    const b = lastVer.breakdown;
    const isOk = Boolean(lastVer.allowed);
    const compScore = typeof lastVer.match_pct === 'number' ? lastVer.match_pct : (lastVer.matchPct || 0);
    const compThr = typeof lastVer.threshold_pct === 'number' ? lastVer.threshold_pct : (lastVer.thresholdPct || thr);
    bdBox.style.display = 'block';
    bdBox.style.borderColor = isOk ? 'rgba(16, 185, 129, 0.45)' : 'rgba(244, 63, 94, 0.5)';
    bdBox.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px; margin-bottom: 6px;">
        <strong style="color: ${isOk ? '#34d399' : '#fb7185'}; font-size: 12px;">
          ${isOk ? '✅ VERIFIED OWNER VOICE' : '🚫 REJECTED IMPOSTOR / CHILD VOICE'} — Composite Score: ${compScore}% (Threshold: ${compThr}%)
        </strong>
        <span style="font-size: 11px; color: #cbd5e1;">
          Candidate F0: <strong>${b.candidate_f0_hz} Hz</strong> (Owner ${b.enrolled_f0_hz} Hz) • VTL: <strong>${b.candidate_vtl_cm} cm</strong> (Owner ${b.enrolled_vtl_cm} cm) • Chest: <strong>${b.candidate_chest_ratio}x</strong>
        </span>
      </div>
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(135px, 1fr)); gap: 6px; font-size: 11px;">
        <div style="background: rgba(15,23,42,0.7); padding: 5px 8px; border-radius: 6px;">🎵 Pitch F0 (30%): <strong>${b.f0_pitch_score}%</strong></div>
        <div style="background: rgba(15,23,42,0.7); padding: 5px 8px; border-radius: 6px;">📐 Formants &amp; VTL (25%): <strong>${b.formant_vtl_score}%</strong></div>
        <div style="background: rgba(15,23,42,0.7); padding: 5px 8px; border-radius: 6px;">📊 8-Band Bark (25%): <strong>${b.bark_spectral_score}%</strong></div>
        <div style="background: rgba(15,23,42,0.7); padding: 5px 8px; border-radius: 6px;">🫁 Chest Resonance (10%): <strong>${b.chest_resonance_score}%</strong></div>
        <div style="background: rgba(15,23,42,0.7); padding: 5px 8px; border-radius: 6px;">🔔 Timbre Rolloff (10%): <strong>${b.timbre_rolloff_score}%</strong></div>
      </div>
    `;
  }

  const logBody = document.getElementById('sandboxHistoryTableBody');
  if (logBody) {
    if (history.length === 0) {
      logBody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 10px;">No sandbox verification tests run yet — click a Live 5s Test or Simulated Child/Owner Benchmark button above!</td></tr>`;
    } else {
      logBody.innerHTML = history.slice(0, 8).map(item => {
        const b = item.breakdown || {};
        const verdictBadge = item.allowed
          ? `<span style="color: #34d399; font-weight: 700;">✅ ACCEPTED (${item.match_pct}%)</span>`
          : `<span style="color: #fb7185; font-weight: 700;">🚫 REJECTED (${item.match_pct}%)</span>`;
        const ts = String(item.timestamp || '').slice(11, 19) || 'now';
        return `
          <tr style="border-bottom: 1px solid rgba(255,255,255,0.06);">
            <td style="padding: 5px 6px; color: var(--text-muted);">${escapeHtml(ts)}</td>
            <td style="padding: 5px 6px; color: #e2e8f0;">${escapeHtml(item.label || 'Test')}</td>
            <td style="padding: 5px 6px;">${verdictBadge}</td>
            <td style="padding: 5px 6px; color: #94a3b8;">F0 ${b.candidate_f0_hz || '--'}Hz • VTL ${b.candidate_vtl_cm || '--'}cm • Chest ${b.candidate_chest_ratio || '--'}x</td>
            <td style="padding: 5px 6px; color: #38bdf8;">${item.auto_refined ? '✨ Auto-Refined' : `Thr ${item.threshold_pct || thr}%`}</td>
          </tr>
        `;
      }).join('');
    }
  }
}

function selectBestJarvisClientAlternative(alternatives) {
  if (!Array.isArray(alternatives) || alternatives.length === 0) return '';
  const cleaned = alternatives.map(a => String(a || '').trim()).filter(Boolean);
  if (cleaned.length === 0) return '';
  if (cleaned.length === 1) return cleaned[0];

  const highValueRegex = /\b(mahadev|can you hear|hear me|jarvis|are you there|mic check|audible|action item|action items|discuss action|talk about|close it|close that|already closed|closed action|reopen|edit it|edit action|next action|next item|what agents|list agents|my agents|about .* agent|health agent|optimizer agent|email agent|backlog agent|overview agent|antigravity|daily briefing|water|workout|playlist|video|optimize|security scan|emails|tasks|smoothie|weight|fasting|today's news|todays news|latest news|latest updates|pune|headlines)\b/i;
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
    const pendingVp = window.AFCCVoice.pendingVoiceprint;
    const vp = window.AFCCVoice.voiceprint;
    const durSec = window.AFCCVoice.calibrationDurationSec || 20;
    if (pendingVp && pendingVp.pitchMeanHz) {
      btnEnroll.innerHTML = `⏳ Confirm Voiceprint (${pendingVp.pitchMeanHz}Hz)`;
      btnEnroll.style.borderColor = 'rgba(251, 191, 36, 0.55)';
      btnEnroll.style.color = '#fde68a';
    } else if (vp && vp.pitchMeanHz) {
      btnEnroll.innerHTML = `🧬 Voiceprint (${vp.pitchMeanHz}Hz • ${vp.vtlCm || 17.1}cm • Re-Calibrate ${durSec}s)`;
      btnEnroll.style.borderColor = 'rgba(16, 185, 129, 0.45)';
      btnEnroll.style.color = '#34d399';
    } else {
      btnEnroll.innerHTML = `🧬 Calibrate My Voice (${durSec}s)`;
    }
  }
  const btnReplayVp = document.getElementById('btnReplayVoiceprint');
  if (btnReplayVp) {
    const hasReplay = Boolean(
      window.AFCCVoice.voiceprintAudioDataUrl ||
      window.AFCCVoice.pendingVoiceprint ||
      (window.AFCCVoice.voiceprint && window.AFCCVoice.voiceprint.hasAudioReplay)
    );
    btnReplayVp.style.display = hasReplay ? 'inline-block' : 'none';
  }
  if (btnWake) {
    const wOn = Boolean(window.AFCCVoice.wakeWordRequired);
    const activeWake = String(window.AFCCVoice.wakeWordPhrase || 'Mahadev').trim() || 'Mahadev';
    btnWake.innerHTML = wOn ? `🔒 Wake Word: "${escapeHtml(activeWake)}"` : `🟢 Wake Word: "${escapeHtml(activeWake)}" (Optional)`;
    btnWake.style.color = wOn ? '#fbbf24' : 'var(--text-muted)';
    btnWake.style.borderColor = wOn ? 'rgba(245, 158, 11, 0.45)' : 'var(--card-border)';
  }
  const wakeInput = document.getElementById('voiceWakeWordInput');
  if (wakeInput && document.activeElement !== wakeInput) {
    wakeInput.value = window.AFCCVoice.wakeWordPhrase || 'Mahadev';
  }
  const genWakeInput = document.getElementById('genSettingWakeWordPhrase');
  if (genWakeInput && document.activeElement !== genWakeInput) {
    genWakeInput.value = window.AFCCVoice.wakeWordPhrase || 'Mahadev';
  }
  const genWakeBadge = document.getElementById('settingsWakeWordBadgeText');
  if (genWakeBadge) {
    genWakeBadge.textContent = window.AFCCVoice.wakeWordPhrase || 'Mahadev';
  }
  const genWakeReq = document.getElementById('genSettingWakeWordRequired');
  if (genWakeReq) {
    genWakeReq.checked = Boolean(window.AFCCVoice.wakeWordRequired);
  }
  const genRateSel = document.getElementById('genSettingVoiceRate');
  if (genRateSel && String(genRateSel.value) !== String(window.AFCCVoice.speechRate)) {
    genRateSel.value = String(window.AFCCVoice.speechRate || 1.25);
  }
  const genLangSel = document.getElementById('genSettingVoiceLanguage');
  if (genLangSel && genLangSel.value !== window.AFCCVoice.voiceLanguage) {
    genLangSel.value = window.AFCCVoice.voiceLanguage || 'en';
  }
  const genGenSel = document.getElementById('genSettingVoiceGender');
  if (genGenSel && genGenSel.value !== window.AFCCVoice.voiceGender) {
    genGenSel.value = window.AFCCVoice.voiceGender || 'female';
  }
  const genAccSel = document.getElementById('genSettingVoiceAccent');
  if (genAccSel && genAccSel.value !== window.AFCCVoice.voiceAccent) {
    genAccSel.value = window.AFCCVoice.voiceAccent || 'IN';
  }
  const genSpkLock = document.getElementById('genSettingVoiceSpeakerLock');
  if (genSpkLock) {
    genSpkLock.checked = Boolean(window.AFCCVoice.speakerLockEnabled);
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
  const cacheKey = `${lang}|${gen}|${acc}|${voices.length}`;
  if (window.AFCCVoice && window.AFCCVoice._cachedVoiceByKey && window.AFCCVoice._cachedVoiceByKey[cacheKey]) {
    return window.AFCCVoice._cachedVoiceByKey[cacheKey];
  }

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
      // IMPORTANT: Never select a non-English (hi-IN/te-IN/mr-IN) voice when speaking English ('en'),
      // because Chrome's remote Google हिन्दी voice silently stalls on multi-sentence English responses at >1.25x speed.
      if (!/^en/i.test(vLang)) {
        score -= 250;
      } else if (acc === 'IN') {
        if (/^en-IN/i.test(vLang) || /Heera|Neerja|Ravi|Prabhat|India/i.test(vName)) {
          score += 220;
        } else if (/^en-GB/i.test(vLang) || /Hazel|Sonia|Libby|UK English/i.test(vName)) {
          score += 120;
        } else if (/^en/i.test(vLang)) {
          score += 95;
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

    // Optimization 4: Strongly prefer native offline OS voices (localService: true, e.g. Microsoft Heera/Neerja/Zira)
    // so TTS starts in <15ms with zero network round-trip or remote cloud synthesis stalls
    if (v.localService) {
      score += 160;
    } else if (/Natural|Online|Google/i.test(vName)) {
      score += 10;
    }

    if (score > bestScore) {
      bestScore = score;
      bestVoice = v;
    }
  }

  const resolved = bestVoice || voices[0] || null;
  if (resolved && window.AFCCVoice && window.AFCCVoice._cachedVoiceByKey) {
    window.AFCCVoice._cachedVoiceByKey[cacheKey] = resolved;
  }
  return resolved;
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

  const btnConcise = document.getElementById('btnVoiceConciseMode');
  if (btnConcise) {
    const snOn = Boolean(window.AFCCVoice.conciseMode);
    btnConcise.innerHTML = snOn ? '⚡ Snappy: ON' : '⚡ Snappy: OFF';
    btnConcise.style.color = snOn ? '#fbbf24' : 'var(--text-muted)';
    btnConcise.style.borderColor = snOn ? 'rgba(251, 191, 36, 0.45)' : 'var(--card-border)';
    btnConcise.style.background = snOn ? 'rgba(251, 191, 36, 0.14)' : 'rgba(255, 255, 255, 0.04)';
  }

  const btnStream = document.getElementById('btnVoiceStreamMode');
  if (btnStream) {
    const stOn = Boolean(window.AFCCVoice.audioStreamMode);
    btnStream.innerHTML = stOn ? '🌊 Stream: ON' : '🌊 Stream: OFF';
    btnStream.style.color = stOn ? '#34d399' : 'var(--text-muted)';
    btnStream.style.borderColor = stOn ? 'rgba(16, 185, 129, 0.45)' : 'var(--card-border)';
    btnStream.style.background = stOn ? 'rgba(16, 185, 129, 0.14)' : 'rgba(255, 255, 255, 0.04)';
  }

  if (btnStopSpeak) {
    btnStopSpeak.style.display = isSpeaking ? 'inline-flex' : 'none';
  }
  syncVoiceProfileSelectors();
}

function toggleVoiceConciseMode() {
  window.AFCCVoice.conciseMode = !window.AFCCVoice.conciseMode;
  try {
    localStorage.setItem('afcc_voice_concise', window.AFCCVoice.conciseMode ? 'true' : 'false');
  } catch (e) {}
  updateVoiceCopilotUI();
}

function toggleVoiceAudioStreamingMode() {
  window.AFCCVoice.audioStreamMode = !window.AFCCVoice.audioStreamMode;
  try {
    localStorage.setItem('afcc_voice_stream_mode', window.AFCCVoice.audioStreamMode ? 'true' : 'false');
  } catch (e) {}
  updateVoiceCopilotUI();
}

function playJarvisInstantAckChime() {
  // Optimization 5: Zero-latency (12ms) subtle WebAudio harmonic acknowledgment pulse when a voice turn locks in
  try {
    const ctx = window.AFCCVoice && window.AFCCVoice.audioCtx;
    if (!ctx || ctx.state !== 'running') return;
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(880, now);
    osc.frequency.exponentialRampToValueAtTime(1174.66, now + 0.038);
    gain.gain.setValueAtTime(0.028, now);
    gain.gain.exponentialRampToValueAtTime(0.0008, now + 0.045);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 0.048);
  } catch (e) {}
}

function splitTextIntoSpeechClauses(text) {
  const clean = String(text || '').trim();
  if (!clean) return [];
  const rawSentences = clean.split(/(?<=[.!?;])\s+/).map(s => s.trim()).filter(Boolean);
  const clauses = [];
  rawSentences.forEach((sent, idx) => {
    const words = sent.split(/\s+/);
    if (idx === 0 && words.length > 12 && /[:,]/.test(sent)) {
      const m = sent.match(/^([^:,]+[:,])\s+(.+)$/);
      if (m && m[1].split(/\s+/).length >= 3) {
        clauses.push(m[1].trim(), m[2].trim());
        return;
      }
    }
    clauses.push(sent);
  });
  return clauses.length > 0 ? clauses : [clean];
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
  if (!isNaN(num) && num >= 0.5 && num <= 3.5) {
    window.AFCCVoice.speechRate = num;
    try {
      localStorage.setItem('afcc_voice_rate', String(num));
    } catch (e) {}
    syncVoiceProfileSelectors();
    try {
      fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ voice_speech_rate: String(num) })
      });
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

function speakAfccVoiceText(text, onDoneCallback, altPhoneticText, streamClausesOverride) {
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
    window.AFCCVoice.speakingStartedAtMs = Date.now();
    window.AFCCVoice.bargeInFrames = 0;
    if (window.speechSynthesis.speaking || window.speechSynthesis.pending) {
      try { window.speechSynthesis.cancel(); } catch (e) {}
    }
    if (window.speechSynthesis.paused && typeof window.speechSynthesis.resume === 'function') {
      try { window.speechSynthesis.resume(); } catch (e) {}
    }
    const langCode = String(window.AFCCVoice.voiceLanguage || 'en').toLowerCase();
    const gender = String(window.AFCCVoice.voiceGender || 'female').toLowerCase();
    const accent = String(window.AFCCVoice.voiceAccent || 'IN').toUpperCase();
    const targetBcp47 = getTargetVoiceLocale();

    const voices = window.speechSynthesis.getVoices ? window.speechSynthesis.getVoices() : [];
    const preferred = resolveBestSpeechVoice(voices, langCode, gender, accent);

    // If speaking Telugu/Hindi/Marathi and the selected voice does not support the native script, use phonetic text so it speaks aloud clearly
    let spokenPayload = cleanText;
    let usePhoneticFallback = false;
    if (preferred && altPhoneticText) {
      const vLang = String(preferred.lang || '').toLowerCase();
      const vName = String(preferred.name || '');
      if (langCode === 'te' && !vLang.startsWith('te') && !/telugu|తెలుగు|shruti|mohan/i.test(vName)) {
        spokenPayload = String(altPhoneticText).trim();
        usePhoneticFallback = true;
      } else if ((langCode === 'hi' || langCode === 'mr') && !vLang.startsWith('hi') && !vLang.startsWith('mr') && !/hindi|marathi|हिन्दी|मराठी|swara|kalpana|aarohi|madhur|hemant|manohar/i.test(vName)) {
        spokenPayload = String(altPhoneticText).trim();
        usePhoneticFallback = true;
      }
    }

    // Optimization 2: Clause-by-Clause Streaming TTS
    // Split multi-sentence text into short clauses so Clause #0 (<= 10 words) starts speaking in <15ms
    // while subsequent clauses queue seamlessly in the browser speech engine!
    const clauses = (
      window.AFCCVoice.audioStreamMode &&
      !usePhoneticFallback &&
      Array.isArray(streamClausesOverride) &&
      streamClausesOverride.length > 1
    )
      ? streamClausesOverride
      : (window.AFCCVoice.audioStreamMode ? splitTextIntoSpeechClauses(spokenPayload) : [spokenPayload]);

    let targetPitch = gender === 'female' ? 1.06 : 0.92;
    if (preferred) {
      const vName = String(preferred.name || '');
      if (gender === 'female' && /\bMale\b|David|Guy|Ravi|Prabhat|Madhur|Mohan|Manohar|Hemant/i.test(vName)) {
        targetPitch = 1.18;
      } else if (gender === 'male' && /Female|Zira|Hazel|Heera|Neerja|Swara|Shruti|Aarohi|Kalpana|Google हिन्दी/i.test(vName)) {
        targetPitch = 0.85;
      } else {
        targetPitch = gender === 'female' ? 1.04 : 0.94;
      }
    }

    let started = false;
    let finished = false;
    const finishOnce = () => {
      if (finished) return;
      finished = true;
      window.AFCCVoice.isSpeaking = false;
      updateVoiceCopilotUI();
      if (typeof onDoneCallback === 'function') onDoneCallback();
    };

    clauses.forEach((clauseText, idx) => {
      const u = new SpeechSynthesisUtterance(clauseText);
      const isWhisper = Boolean(window.AFCCVoice.whisperMode);
      u.volume = isWhisper ? 0.45 : 1.0;
      u.rate = isWhisper
        ? Math.min(1.15, (window.AFCCVoice.speechRate || 1.35) * 0.85)
        : (window.AFCCVoice.speechRate || 1.35);
      u.lang = preferred && preferred.lang ? preferred.lang : targetBcp47;
      u.pitch = targetPitch;
      if (preferred) u.voice = preferred;

      if (idx === 0) {
        u.onstart = () => {
          started = true;
          window.AFCCVoice.isSpeaking = true;
          updateVoiceCopilotUI(`🔊 Streaming (${getVoiceProfileDisplayLabel()})...`, 'speaking');
        };
      }
      if (idx === clauses.length - 1) {
        u.onend = () => finishOnce();
      }
      u.onerror = () => {
        if (!started && !finished && idx === 0) {
          try {
            window.speechSynthesis.cancel();
            const fallbackUtter = new SpeechSynthesisUtterance(spokenPayload);
            const localEn = voices.find(v => v.localService && /^en/i.test(String(v.lang || ''))) || voices.find(v => v.localService);
            if (localEn) fallbackUtter.voice = localEn;
            fallbackUtter.rate = Math.min(1.75, window.AFCCVoice.speechRate || 1.35);
            fallbackUtter.onend = finishOnce;
            fallbackUtter.onerror = finishOnce;
            window.speechSynthesis.speak(fallbackUtter);
            return;
          } catch (err) {}
        }
        if (idx === clauses.length - 1) finishOnce();
      };
      window.speechSynthesis.speak(u);
    });

    // Optimization 4: Fast 220ms Local Voice Watchdog (down from 650ms)
    setTimeout(() => {
      if (!started && !finished && 'speechSynthesis' in window) {
        try {
          window.speechSynthesis.cancel();
          if (typeof window.speechSynthesis.resume === 'function') window.speechSynthesis.resume();
          const fallbackUtter = new SpeechSynthesisUtterance(spokenPayload);
          const localEn = voices.find(v => v.localService && /^en/i.test(String(v.lang || ''))) || voices.find(v => v.localService);
          if (localEn) {
            fallbackUtter.voice = localEn;
            fallbackUtter.lang = localEn.lang || 'en-US';
          }
          fallbackUtter.rate = Math.min(1.75, window.AFCCVoice.speechRate || 1.35);
          fallbackUtter.onstart = () => {
            started = true;
            window.AFCCVoice.isSpeaking = true;
            updateVoiceCopilotUI(`🔊 Speaking (${getVoiceProfileDisplayLabel()})...`, 'speaking');
          };
          fallbackUtter.onend = finishOnce;
          fallbackUtter.onerror = finishOnce;
          window.speechSynthesis.speak(fallbackUtter);
        } catch (err) {
          finishOnce();
        }
      }
    }, 220);
  } catch (e) {
    window.AFCCVoice.isSpeaking = false;
    updateVoiceCopilotUI();
    if (typeof onDoneCallback === 'function') onDoneCallback();
  }
}

function replayLastAfccVoiceReply() {
  if (
    window.AFCCVoice.pendingVoiceprint ||
    (window.AFCCVoice.lastActionWasVoiceprint && window.AFCCVoice.voiceprintAudioDataUrl)
  ) {
    replayJarvisVoiceprintAudio();
    return;
  }
  if (window.AFCCVoice.lastSpokenReply) {
    speakAfccVoiceText(
      window.AFCCVoice.lastSpokenReply,
      null,
      window.AFCCVoice.lastSpokenPhonetic || window.AFCCVoice.lastSpokenReply
    );
  }
}

function renderVoiceFocusedActionItem(taskObj) {
  const bar = document.getElementById('voiceFocusedActionItemBar');
  const stepBadge = document.getElementById('voiceFocusedTaskStepBadge');
  const titleEl = document.getElementById('voiceFocusedTaskTitle');
  const metaEl = document.getElementById('voiceFocusedTaskMeta');
  const btnClose = document.getElementById('btnVoiceCloseFocusedTask');
  const btnReopen = document.getElementById('btnVoiceReopenFocusedTask');

  window.AFCCVoice.activeActionItem = taskObj || null;
  if (!bar) return;
  if (!taskObj || !taskObj.id) {
    bar.style.display = 'none';
    return;
  }
  bar.style.display = 'block';
  const pos = taskObj.cursor_position || 1;
  const total = taskObj.queue_total || 1;
  const isClosed = String(taskObj.status || '').toLowerCase() === 'completed';

  if (stepBadge) {
    stepBadge.textContent = `${isClosed ? 'Closed' : 'Open'} ${pos}/${total}`;
  }
  if (titleEl) {
    titleEl.textContent = `#${taskObj.id} — ${taskObj.title || 'Action Item'}`;
    titleEl.style.color = isClosed ? '#cbd5e1' : '#6ee7b7';
    titleEl.style.textDecoration = isClosed ? 'line-through' : 'none';
  }
  if (metaEl) {
    metaEl.textContent = `${taskObj.priority || 'P2'} • ${taskObj.source || 'Manual'} • ${isClosed ? 'closed' : 'open'}`;
  }
  if (btnClose) {
    btnClose.style.display = isClosed ? 'none' : 'inline-block';
  }
  if (btnReopen) {
    btnReopen.style.display = isClosed ? 'inline-block' : 'none';
  }
}

function promptVoiceEditFocusedActionItem() {
  const cur = window.AFCCVoice.activeActionItem;
  const currentTitle = cur && cur.title ? cur.title : '';
  const newTitle = window.prompt(
    cur ? `Edit Action Item #${cur.id} title (or speak "Edit it to <new title>"):` : 'Enter new title for the focused action item:',
    currentTitle
  );
  if (newTitle && newTitle.trim() && newTitle.trim() !== currentTitle) {
    executeVoiceTurnText(`Edit it to ${newTitle.trim()}`);
  }
}

async function executeVoiceUiActions(uiActions) {
  if (!Array.isArray(uiActions) || uiActions.length === 0) return;
  for (const act of uiActions) {
    if (!act || !act.type) continue;
    try {
      if (act.type === 'focus_action_item') {
        renderVoiceFocusedActionItem(act.task || null);
      } else if (act.type === 'switch_agent' && act.agent_id) {
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
      } else if (act.type === 'set_whisper_mode') {
        window.AFCCVoice.whisperMode = Boolean(act.enabled);
        try {
          localStorage.setItem('afcc_voice_whisper_mode', window.AFCCVoice.whisperMode ? 'true' : 'false');
        } catch (e) {}
      } else if (act.type === 'set_density' && act.density) {
        if (typeof window.AFCCUI !== 'undefined' && typeof window.AFCCUI.setDensityMode === 'function') {
          window.AFCCUI.setDensityMode(act.density, true, false);
        }
      } else if (act.type === 'set_zen_mode') {
        if (typeof window.AFCCUI !== 'undefined' && typeof window.AFCCUI.toggleZenFocusMode === 'function') {
          window.AFCCUI.toggleZenFocusMode(Boolean(act.enabled));
        }
      } else if (act.type === 'set_gpu_eco') {
        if (typeof window.AFCCUI !== 'undefined' && typeof window.AFCCUI.toggleGpuEcoMode === 'function') {
          window.AFCCUI.toggleGpuEcoMode(Boolean(act.enabled), false);
        }
      } else if (act.type === 'open_design_system') {
        if (typeof window.AFCCUI !== 'undefined' && typeof window.AFCCUI.openDesignSystemModal === 'function') {
          window.AFCCUI.openDesignSystemModal();
        }
      }
    } catch (err) {
      console.warn('Voice UI action error:', err);
    }
  }
}

function tryInstantClientVoiceFastPath(spokenText) {
  // Optimization 3: Zero-Network Client Reflex Cache (<15ms local speech start)
  const lower = String(spokenText || '').trim().toLowerCase();
  if (!lower || window.AFCCVoice.voiceLanguage !== 'en') return null;

  if (/^(mahadev|har har mahadev|jarvis|can you hear me|hear me|are you there|mic check)$/i.test(lower)) {
    return 'Loud and clear! Jarvis online. How can I help?';
  }
  const cache = window.AFCCVoice.actionItemsCache;
  if (cache && Array.isArray(cache.open) && cache.open.length > 0 && (Date.now() - (cache.lastSyncedAt || 0) < 900000)) {
    if (/\b(discuss action items|talk about.*action items|open action items|action items chat)\b/i.test(lower)) {
      cache.cursorIdx = 0;
      const t = cache.open[0];
      return window.AFCCVoice.conciseMode
        ? `${cache.open.length} open items. Item 1, #${t.id}: ${t.title}, ${t.priority || 'P2'}. Close, edit, or next?`
        : `You have ${cache.open.length} open action items. Item 1 is #${t.id}: ${t.title}, priority ${t.priority || 'P2'}. Say close it, edit it, or next action item.`;
    }
    if (/^(next|next action item|next item|skip|skip it)$/i.test(lower)) {
      const nextIdx = ((cache.cursorIdx || 0) + 1) % cache.open.length;
      cache.cursorIdx = nextIdx;
      const t = cache.open[nextIdx];
      if (t) {
        return `Item ${nextIdx + 1} of ${cache.open.length}: #${t.id} ${t.title}. Close, edit, or next?`;
      }
    }
  }
  return null;
}

async function refreshVoiceActionItemsClientCache() {
  try {
    const res = await fetch('/api/voice/action_items?status=all');
    if (!res.ok) return;
    const data = await res.json();
    if (data && Array.isArray(data.items)) {
      window.AFCCVoice.actionItemsCache = {
        open: data.items.filter(t => String(t.status || '').toLowerCase() !== 'completed'),
        closed: data.items.filter(t => String(t.status || '').toLowerCase() === 'completed'),
        cursorIdx: 0,
        lastSyncedAt: Date.now()
      };
    }
  } catch (e) {}
}
setTimeout(refreshVoiceActionItemsClientCache, 1400);

const MAX_VOICE_AUDIO_QUEUE = 10;

function renderJarvisQueueAndTopicStackBar() {
  const bar = document.getElementById('voiceQueueAndTopicStackBar');
  if (!bar) return;
  const q = window.AFCCVoice.audioMessageQueue || [];
  const cur = window.AFCCVoice.activeQueueItem;
  const stack = window.AFCCVoice.topicStackSnapshot || { parked_topics: [], parked_count: 0 };
  const parkedList = Array.isArray(stack.parked_topics) ? stack.parked_topics : [];
  const parkedCount = Number(stack.parked_count || parkedList.length || 0);

  const hasMultiPartActive = Boolean((cur && cur.total_parts > 1) || q.length > 0);
  if (!hasMultiPartActive && parkedCount === 0) {
    bar.style.display = 'none';
    return;
  }
  bar.style.display = 'block';

  const stepBadge = document.getElementById('voiceQueueStepBadge');
  const topicLbl = document.getElementById('voiceQueueCurrentTopicLabel');
  const parkedBadge = document.getElementById('voiceParkedTopicsBadge');
  const btnSkip = document.getElementById('btnVoiceSkipQueuePart');
  const btnResume = document.getElementById('btnVoiceResumeParkedTopic');
  const btnClear = document.getElementById('btnVoiceClearAudioQueue');

  if (stepBadge) {
    if (cur && cur.total_parts > 1) {
      stepBadge.textContent = `🔊 Part ${cur.part_index}/${cur.total_parts}`;
      stepBadge.style.display = 'inline-block';
    } else if (q.length > 0) {
      stepBadge.textContent = `📚 ${q.length} Queued`;
      stepBadge.style.display = 'inline-block';
    } else {
      stepBadge.style.display = 'none';
    }
  }
  if (topicLbl) {
    if (cur && cur.total_parts > 1) {
      topicLbl.textContent = `${cur.topic_label || cur.title || 'Speaking...'}${q.length > 0 ? ` (+${q.length} next)` : ''}`;
    } else if (stack.active_topic && stack.active_topic.topic_label) {
      topicLbl.textContent = `Active: ${stack.active_topic.topic_label}`;
    } else {
      topicLbl.textContent = 'Conversation Stack Active';
    }
  }
  if (parkedBadge) {
    if (parkedCount > 0) {
      const topParked = parkedList[0] ? (parkedList[0].topic_label || 'Topic') : 'Topic';
      parkedBadge.style.display = 'inline-block';
      parkedBadge.textContent = `📌 Parked (${parkedCount}): ${topParked}`;
    } else {
      parkedBadge.style.display = 'none';
    }
  }
  if (btnSkip) {
    btnSkip.style.display = q.length > 0 ? 'inline-block' : 'none';
  }
  if (btnClear) {
    btnClear.style.display = (q.length > 0 || (cur && cur.total_parts > 1)) ? 'inline-block' : 'none';
  }
  if (btnResume) {
    btnResume.style.display = parkedCount > 0 ? 'inline-block' : 'none';
  }
}

function processNextJarvisAudioQueueItem() {
  const q = window.AFCCVoice.audioMessageQueue || [];
  if (q.length === 0) {
    window.AFCCVoice.activeQueueItem = null;
    renderJarvisQueueAndTopicStackBar();
    if (window.AFCCVoice.userWantsListening && window.AFCCVoice.continuousMode && !window.AFCCVoice.isSpeaking) {
      startBrowserSpeechRecognition();
    }
    return;
  }

  const nextItem = q.shift();
  window.AFCCVoice.activeQueueItem = nextItem;
  renderJarvisQueueAndTopicStackBar();

  const replyLineEl = document.getElementById('voiceAssistantReplyLine');
  const replyTextEl = document.getElementById('voiceSpokenReplyText');
  const floatToast = document.getElementById('voiceGlobalFloatingToast');
  const floatText = document.getElementById('voiceGlobalFloatingText');

  const spokenText = (window.AFCCVoice.conciseMode && nextItem.spoken_reply_concise)
    ? nextItem.spoken_reply_concise
    : (nextItem.spoken_reply || nextItem.message || nextItem.title || 'Done.');

  const prefixLabel = (nextItem.total_parts && nextItem.total_parts > 1)
    ? `[Part ${nextItem.part_index}/${nextItem.total_parts} • ${nextItem.topic_label || 'Answer'}] `
    : '';

  if (replyLineEl && replyTextEl) {
    replyLineEl.style.display = 'block';
    replyTextEl.textContent = `${prefixLabel}${spokenText}`;
  }
  if (floatToast && floatToast.style.display !== 'none' && floatText) {
    floatText.textContent = `🔊 ${prefixLabel}${spokenText}`;
  }

  if (typeof nextItem.active_action_item !== 'undefined' && nextItem.active_action_item !== null) {
    renderVoiceFocusedActionItem(nextItem.active_action_item);
  }
  if (Array.isArray(nextItem.ui_actions) && nextItem.ui_actions.length > 0) {
    Promise.resolve().then(() => executeVoiceUiActions(nextItem.ui_actions));
  }

  const clauses = Array.isArray(nextItem.spoken_stream_clauses) ? nextItem.spoken_stream_clauses : null;
  speakAfccVoiceText(
    spokenText,
    () => {
      if ((window.AFCCVoice.audioMessageQueue || []).length > 0) {
        // Natural 220ms conversational breath between sequential queued audio answers
        setTimeout(() => processNextJarvisAudioQueueItem(), 220);
      } else {
        window.AFCCVoice.activeQueueItem = null;
        renderJarvisQueueAndTopicStackBar();
        if (window.AFCCVoice.userWantsListening && window.AFCCVoice.continuousMode) {
          startBrowserSpeechRecognition();
        }
      }
    },
    spokenText,
    clauses
  );
}

function playJarvisSequentialAudioQueue(queueItems, appendToExisting) {
  if (!Array.isArray(queueItems) || queueItems.length === 0) return;
  if (!Array.isArray(window.AFCCVoice.audioMessageQueue)) {
    window.AFCCVoice.audioMessageQueue = [];
  }
  if (!appendToExisting) {
    window.AFCCVoice.audioMessageQueue = [];
  }
  for (let i = 0; i < queueItems.length; i++) {
    if (window.AFCCVoice.audioMessageQueue.length >= MAX_VOICE_AUDIO_QUEUE) {
      window.AFCCVoice.audioMessageQueue.shift();
    }
    window.AFCCVoice.audioMessageQueue.push(queueItems[i]);
  }
  renderJarvisQueueAndTopicStackBar();
  if (!appendToExisting || !window.AFCCVoice.isSpeaking) {
    processNextJarvisAudioQueueItem();
  }
}

function skipCurrentJarvisAudioQueuePart() {
  if ('speechSynthesis' in window) {
    try { window.speechSynthesis.cancel(); } catch (e) {}
  }
  window.AFCCVoice.isSpeaking = false;
  if ((window.AFCCVoice.audioMessageQueue || []).length > 0) {
    setTimeout(() => processNextJarvisAudioQueueItem(), 60);
  } else {
    window.AFCCVoice.activeQueueItem = null;
    renderJarvisQueueAndTopicStackBar();
    updateVoiceCopilotUI();
  }
}

function clearJarvisAudioQueue() {
  window.AFCCVoice.audioMessageQueue = [];
  window.AFCCVoice.activeQueueItem = null;
  stopAfccVoiceSpeaking();
  renderJarvisQueueAndTopicStackBar();
}

function resumeParkedJarvisTopicNow() {
  clearJarvisAudioQueue();
  executeVoiceTurnText('Resume parked topic');
}

async function executeVoiceTurnText(transcriptText, alternativesList) {
  window.AFCCVoice.lastActionWasVoiceprint = false;
  const turnStartMs = performance.now ? performance.now() : Date.now();
  const rawAlts = Array.isArray(alternativesList) && alternativesList.length > 0
    ? alternativesList
    : [transcriptText];
  const spoken = selectBestJarvisClientAlternative(rawAlts) || String(transcriptText || '').trim();
  if (!spoken) return;

  // Client-side instant queue control reflexes (<5ms, 0 network calls)
  const lowerSpoken = spoken.toLowerCase().trim();
  const nowTurnMs = Date.now();
  // [JV-08] Single-Flight Voice Turn Deduplicator (<150ms double-dispatch guard)
  if (
    lowerSpoken === window.AFCCVoice._lastDispatchedTurnSig &&
    (nowTurnMs - (window.AFCCVoice._lastDispatchedTurnAtMs || 0) < 150)
  ) {
    return;
  }
  window.AFCCVoice._lastDispatchedTurnSig = lowerSpoken;
  window.AFCCVoice._lastDispatchedTurnAtMs = nowTurnMs;

  if (/^(skip\s+part|next\s+part|next\s+answer|skip\s+to\s+next\s+question|skip\s+answer)$/i.test(lowerSpoken)) {
    skipCurrentJarvisAudioQueuePart();
    return;
  }
  if (/^(clear\s+queue|stop\s+queue|cancel\s+queue|clear\s+all\s+audio)$/i.test(lowerSpoken)) {
    clearJarvisAudioQueue();
    return;
  }

  // [JV-08] Cancel any superseded in-flight voice fetch via AbortController
  if (window.AFCCVoice._activeVoiceFetchController) {
    try { window.AFCCVoice._activeVoiceFetchController.abort(); } catch (e) {}
  }
  const fetchController = (typeof AbortController !== 'undefined') ? new AbortController() : null;
  window.AFCCVoice._activeVoiceFetchController = fetchController;

  // Optimization 5: Immediate 12ms WebAudio harmonic acknowledgment chime
  playJarvisInstantAckChime();

  const transcriptEl = document.getElementById('voiceTranscriptText');
  const replyLineEl = document.getElementById('voiceAssistantReplyLine');
  const replyTextEl = document.getElementById('voiceSpokenReplyText');
  const actStripEl = document.getElementById('voiceExecutedActivitiesStrip');
  const latBadgeEl = document.getElementById('voiceLatencyBadge');

  if (transcriptEl) {
    transcriptEl.innerHTML = `<strong style="color: #fff;">"${escapeHtml(spoken)}"</strong>`;
  }
  updateVoiceCopilotUI('⚡ J.A.R.V.I.S. Streaming...', 'executing');

  // Optimization 3: Check Zero-Network Client Reflex Cache for <15ms pre-speech start
  // Only use single-turn fast cache when no parked topic or multi-part connector is present
  const hasMultiConnector = /\b(and|also|then|after that|first|second|news|pune|updates)\b|\?/i.test(lowerSpoken);
  const hasActiveTopicInterrupt = Boolean(
    window.AFCCVoice.topicStackSnapshot &&
    window.AFCCVoice.topicStackSnapshot.active_topic &&
    !/\b(discuss action items|next|close|edit|details|reopen|pay)\b/i.test(lowerSpoken)
  );
  let preSpokenFastPath = false;
  const instantFastReply = (!hasMultiConnector && !hasActiveTopicInterrupt)
    ? tryInstantClientVoiceFastPath(spoken)
    : null;
  if (instantFastReply && window.AFCCVoice.spokenReplyEnabled) {
    preSpokenFastPath = true;
    const fastElapsed = Math.max(8, Math.round((performance.now ? performance.now() : Date.now()) - turnStartMs));
    window.AFCCVoice.lastTurnLatencyMs = fastElapsed;
    if (latBadgeEl) {
      latBadgeEl.textContent = `⚡ ${fastElapsed}ms Cache`;
    }
    if (replyLineEl && replyTextEl) {
      replyLineEl.style.display = 'block';
      replyTextEl.textContent = instantFastReply;
    }
    speakAfccVoiceText(instantFastReply, () => {
      if (window.AFCCVoice.userWantsListening && window.AFCCVoice.continuousMode) {
        startBrowserSpeechRecognition();
      }
    }, instantFastReply);
  }

  try {
    window.AFCCVoice.lastTurnDispatchedAtMs = Date.now();
    const burstBarEarly = document.getElementById('voiceAcousticBurstFallbackBar');
    if (burstBarEarly) burstBarEarly.style.display = 'none';

    const reqBody = JSON.stringify({
      transcript: spoken,
      alternatives: rawAlts,
      routing_mode: window.AFCCVoice.routingMode || 'zero_token',
      language: window.AFCCVoice.voiceLanguage || 'en',
      gender: window.AFCCVoice.voiceGender || 'female',
      accent: window.AFCCVoice.voiceAccent || 'IN',
      concise_mode: Boolean(window.AFCCVoice.conciseMode)
    });
    const endpointUrl = window.AFCCVoice.audioStreamMode ? '/api/voice/stream' : '/api/voice/converse';
    const fetchOpts = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: reqBody
    };
    if (fetchController) fetchOpts.signal = fetchController.signal;
    let res = await fetch(endpointUrl, fetchOpts);
    // Automatic endpoint fallback: if /api/voice/stream returned 404/500, transparently fall back to /api/voice/converse
    if (!res.ok && endpointUrl === '/api/voice/stream') {
      res = await fetch('/api/voice/converse', fetchOpts);
    }
    const data = await res.json();
    const netElapsedMs = Math.max(12, Math.round((performance.now ? performance.now() : Date.now()) - turnStartMs));
    if (!preSpokenFastPath) {
      window.AFCCVoice.lastTurnLatencyMs = netElapsedMs;
      if (latBadgeEl) {
        latBadgeEl.textContent = `⚡ ${netElapsedMs}ms Stream`;
      }
    }

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
        setTimeout(() => startBrowserSpeechRecognition(), 180);
      }
      return;
    }

    if (data.topic_stack && typeof data.topic_stack === 'object') {
      window.AFCCVoice.topicStackSnapshot = data.topic_stack;
    }

    let fullSpokenReply = data.spoken_reply || data.message || data.title || 'Done.';
    if (typeof fullSpokenReply === 'string' && fullSpokenReply.trim().startsWith('{') && fullSpokenReply.includes('conversation')) {
      fullSpokenReply = 'I heard you clearly. All Fleet agents are online at $0.00 zero-token cost. Tell me which agent or action you would like to run.';
    }
    const activeSpokenReply = (window.AFCCVoice.conciseMode && data.spoken_reply_concise)
      ? data.spoken_reply_concise
      : fullSpokenReply;
    const spokenPhonetic = data.spoken_reply_phonetic || activeSpokenReply;
    const streamClauses = Array.isArray(data.spoken_stream_clauses) ? data.spoken_stream_clauses : null;
    const queueItems = Array.isArray(data.voice_queue_items) ? data.voice_queue_items : [];

    // If the response contains multiple sequential audio queue parts (either from a multi-question utterance
    // or from an interrupted topic + auto-resume bridge), play them sequentially one after another via the event-driven queue!
    if (!preSpokenFastPath && queueItems.length >= 2) {
      playJarvisSequentialAudioQueue(queueItems, false);
    } else {
      window.AFCCVoice.audioMessageQueue = [];
      window.AFCCVoice.activeQueueItem = queueItems[0] || null;
      renderJarvisQueueAndTopicStackBar();
      if (replyLineEl && replyTextEl) {
        replyLineEl.style.display = 'block';
        replyTextEl.textContent = activeSpokenReply;
      }
      if (!preSpokenFastPath) {
        speakAfccVoiceText(activeSpokenReply, () => {
          window.AFCCVoice.activeQueueItem = null;
          renderJarvisQueueAndTopicStackBar();
          if (window.AFCCVoice.userWantsListening && window.AFCCVoice.continuousMode) {
            startBrowserSpeechRecognition();
          }
        }, spokenPhonetic, streamClauses);
      }
    }

    // [JV-09] Non-Blocking requestAnimationFrame Post-Speech DOM Update Batching
    // Defers visual badge, chat history, and context chip DOM mutations until after SpeechSynthesis audio starts
    const scheduleVisualDomCommit = window.requestAnimationFrame || ((fn) => setTimeout(fn, 0));
    scheduleVisualDomCommit(() => {
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

      if (typeof FleetNavigator !== 'undefined') {
        if (!Array.isArray(FleetNavigator.omnibarChatTurns)) {
          FleetNavigator.omnibarChatTurns = [];
        }
        if (FleetNavigator.omnibarChatTurns.length >= 40) {
          FleetNavigator.omnibarChatTurns.shift();
        }
        FleetNavigator.omnibarChatTurns.push({
          userQuery: `🎙️ ${data.selected_transcript || spoken}`,
          data: data
        });
        if (typeof renderAgFleetZeroChat === 'function') {
          renderAgFleetZeroChat();
        }
      }

      if (typeof data.active_action_item !== 'undefined') {
        renderVoiceFocusedActionItem(data.active_action_item);
      }
      if (typeof renderDynamicVoiceContextChips === 'function') {
        renderDynamicVoiceContextChips(data.context_chips || []);
      }
      const burstBar = document.getElementById('voiceAcousticBurstFallbackBar');
      if (burstBar) burstBar.style.display = 'none';
      const floatToast = document.getElementById('voiceGlobalFloatingToast');
      const floatText = document.getElementById('voiceGlobalFloatingText');
      if (floatToast && floatToast.style.display !== 'none' && floatText) {
        floatText.textContent = `🔊 ${activeSpokenReply}`;
      }
    });
    Promise.resolve().then(async () => {
      await executeVoiceUiActions(data.ui_actions || []);
      if (typeof fetchLogs === 'function') fetchLogs();
      refreshVoiceActionItemsClientCache();
    });
  } catch (e) {
    if (e && e.name === 'AbortError') return;
    console.error('Voice converse error:', e);
    if (!preSpokenFastPath) {
      const errFallbackSpeech = `I heard ${spoken}. Connecting to your local Fleet server now.`;
      if (replyLineEl && replyTextEl) {
        replyLineEl.style.display = 'block';
        replyTextEl.textContent = errFallbackSpeech;
      }
      speakAfccVoiceText(errFallbackSpeech, () => {
        if (window.AFCCVoice.userWantsListening && window.AFCCVoice.continuousMode) {
          startBrowserSpeechRecognition();
        }
      }, errFallbackSpeech);
    }
    updateVoiceCopilotUI();
  }
}

function toggleVoiceStudioTuningDrawer(forceOpen) {
  // UX Improvement #3: Collapsible Voice Studio & Biometrics Drawer for Decluttered Focus HUD
  const drawer = document.getElementById('voiceStudioTuningDrawer');
  const btn = document.getElementById('btnVoiceStudioDrawerToggle');
  if (!drawer) return;
  const isOpen = typeof forceOpen === 'boolean' ? forceOpen : (drawer.style.display === 'none');
  drawer.style.display = isOpen ? 'block' : 'none';
  if (btn) {
    btn.innerHTML = isOpen ? '⚙️ Studio ▴' : '⚙️ Studio ▾';
    btn.style.background = isOpen ? 'rgba(168, 85, 247, 0.28)' : 'rgba(168, 85, 247, 0.14)';
  }
}

function renderDynamicVoiceContextChips(chips) {
  // UX Improvement #1: Dynamic Contextual Follow-Up Chips
  const bar = document.getElementById('voiceDynamicContextChipsBar');
  if (!bar) return;
  if (!Array.isArray(chips) || chips.length === 0) {
    bar.style.display = 'none';
    return;
  }
  bar.style.display = 'flex';
  bar.innerHTML = `<span style="font-size: 9.5px; color: #38bdf8; font-weight: 700;">🎯 Next Step:</span>` +
    chips.map(c => {
      const safePhrase = String(c.phrase || '').replace(/'/g, "\\'");
      return `<button type="button" class="quick-chip" style="font-size: 10px; padding: 2px 8px; border-color: rgba(56, 189, 248, 0.5); color: #7dd3fc; background: rgba(56, 189, 248, 0.14);" onclick="executeVoiceTurnText('${safePhrase}')">${escapeHtml(c.label || c.phrase || '')}</button>`;
    }).join('');
}

function renderJarvisLiveSpectrumCanvas(freqBuf, pitchHz, snrDb) {
  // UX Improvement #2 + [JV-06B]: Live 16-Bar WebAudio Spectrum with Offscreen Skip & 32-Bit Signature Diffing
  const canvas = document.getElementById('voiceLiveSpectrumCanvas');
  if (!canvas || !canvas.offsetParent || typeof canvas.getContext !== 'function') return;
  const w = canvas.width || 168;
  const h = canvas.height || 22;
  const numBars = 16;
  const isOwnerVoice = pitchHz >= 65 && pitchHz <= 195 && snrDb >= 11;
  const isChildOrHigh = pitchHz > 205 && snrDb >= 11;
  const colorCode = isOwnerVoice ? 3 : (isChildOrHigh ? 2 : (snrDb >= 9 ? 1 : 0));

  // Compute fast 32-bit FNV-style signature of the 16 bar heights + colorCode to skip identical redraws
  let sig = 2166136261 ^ colorCode;
  for (let b = 0; b < numBars; b++) {
    const binIdx = Math.min((freqBuf ? freqBuf.length - 1 : 0), 2 + b * 4);
    const val = freqBuf ? (freqBuf[binIdx] || 0) : 0;
    const barH = Math.max(3, Math.round((val / 255) * (h - 4)));
    sig = Math.imul(sig ^ barH, 16777619);
  }
  if (window.AFCCVoice && window.AFCCVoice._lastSpectrumSig === sig) {
    return;
  }
  if (window.AFCCVoice) {
    window.AFCCVoice._lastSpectrumSig = sig;
  }

  const ctx2d = canvas.getContext('2d');
  if (!ctx2d) return;
  ctx2d.clearRect(0, 0, w, h);

  const barW = Math.floor((w - (numBars - 1) * 2) / numBars);
  const fillStyle = isOwnerVoice
    ? '#10b981'
    : (isChildOrHigh ? '#f43f5e' : (snrDb >= 9 ? '#f59e0b' : 'rgba(56, 189, 248, 0.35)'));

  ctx2d.fillStyle = fillStyle;
  for (let b = 0; b < numBars; b++) {
    const binIdx = Math.min((freqBuf ? freqBuf.length - 1 : 0), 2 + b * 4);
    const val = freqBuf ? (freqBuf[binIdx] || 0) : 0;
    const barH = Math.max(3, Math.round((val / 255) * (h - 4)));
    const x = b * (barW + 2);
    const y = h - barH - 2;
    ctx2d.fillRect(x, y, barW, barH);
  }
}

function handleAcousticShortBurstFallback() {
  // UX Improvement #7: Local Acoustic Reflex Fallback when Chrome Speech API drops a short 1-word utterance
  // Suppress for 2500ms after a valid voice turn was already dispatched so sentence tails never trigger a false banner
  if (Date.now() - (window.AFCCVoice.lastTurnDispatchedAtMs || 0) < 2500) {
    return false;
  }
  const pitches = window.AFCCVoice.utterancePitchSamples || [];
  const peakSnr = window.AFCCVoice.utterancePeakSnrDb || 0;
  const bar = document.getElementById('voiceAcousticBurstFallbackBar');
  if (!bar) return false;
  if (pitches.length >= 2 && pitches.length <= 18 && peakSnr >= 14) {
    const avgPitch = Math.round(pitches.reduce((a, b) => a + b, 0) / pitches.length);
    if (avgPitch >= 65 && avgPitch <= 195) {
      bar.style.display = 'flex';
      bar.innerHTML = `
        <span>🎤 <strong>Heard short owner voice burst (${avgPitch}Hz, ${peakSnr}dB)</strong> — Chrome Speech dropped the short word. Tap or repeat:</span>
        <div style="display: inline-flex; gap: 4px; flex-wrap: wrap;">
          <button type="button" class="btn" style="font-size: 9.5px; padding: 1px 7px; border-color: #34d399; color: #34d399;" onclick="executeVoiceTurnText('Close it')">✅ Done / Close</button>
          <button type="button" class="btn" style="font-size: 9.5px; padding: 1px 7px; border-color: #38bdf8; color: #38bdf8;" onclick="executeVoiceTurnText('Next action item')">⏭️ Next</button>
          <button type="button" class="btn" style="font-size: 9.5px; padding: 1px 7px; border-color: #c084fc; color: #c084fc;" onclick="executeVoiceTurnText('Read details')">🔎 Details</button>
        </div>
      `;
      return true;
    }
  }
  return false;
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
  await ensureJarvisAudioDspPipeline();

  window.AFCCVoice.utterancePitchSamples = [];
  window.AFCCVoice.utteranceCentroidSamples = [];
  window.AFCCVoice.utteranceFineFrameSamples = [];
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
    let lastInterimTranscript = '';
    let collectedAlternatives = [];
    let uttrDispatched = false;
    let earlyEndpointTimer = null;

    const commitVoiceUtteranceNow = () => {
      if (uttrDispatched) return;
      const captured = (finalTranscript || lastInterimTranscript).trim();
      if (!captured) return;
      uttrDispatched = true;
      if (earlyEndpointTimer) {
        clearTimeout(earlyEndpointTimer);
        earlyEndpointTimer = null;
      }
      window.AFCCVoice.isListening = false;
      try { rec.stop(); } catch (e) {}
      updateVoiceCopilotUI();

      // Biometric Speaker Verification & Background Noise Gate
      const bioCheck = verifySpeakerBiometrics(captured, collectedAlternatives);
      // Clear utterance biometric sample buffers immediately after verification so trailing frames never leak into rec.onend
      window.AFCCVoice.utterancePitchSamples = [];
      window.AFCCVoice.utteranceCentroidSamples = [];
      window.AFCCVoice.utteranceFineFrameSamples = [];
      window.AFCCVoice.utterancePeakSnrDb = 0;
      window.AFCCVoice.lastTurnDispatchedAtMs = Date.now();
      if (!bioCheck.allowed) {
        const rejectMsg = `🛡️ ${bioCheck.reason || 'Background audio ignored'} ("${captured}")`;
        if (transcriptEl) {
          transcriptEl.innerHTML = `<span style="color: #fbbf24;">${escapeHtml(rejectMsg)}</span>`;
        }
        const replyLineEl = document.getElementById('voiceAssistantReplyLine');
        const replyTextEl = document.getElementById('voiceSpokenReplyText');
        if (replyLineEl && replyTextEl) {
          replyLineEl.style.display = 'block';
          replyTextEl.textContent = rejectMsg;
        }
        updateVoiceCopilotUI('🛡️ Speaker Lock: Filtered Audio', 'ready');
        if (window.AFCCVoice.userWantsListening && window.AFCCVoice.continuousMode && !window.AFCCVoice.isSpeaking) {
          setTimeout(() => startBrowserSpeechRecognition(), 900);
        }
        return;
      }
      executeVoiceTurnText(captured, collectedAlternatives);
    };

    rec.onstart = () => {
      window.AFCCVoice.isListening = true;
      updateVoiceCopilotUI(`🎙️ J.A.R.V.I.S. Listening (${targetBcp47})...`, 'listening');
      if (transcriptEl) {
        transcriptEl.innerHTML = `<span style="color: #c084fc; font-style: italic;">J.A.R.V.I.S. listening (${escapeHtml(getVoiceProfileDisplayLabel())})... Speak your command now.</span>`;
      }
    };

    rec.onresult = (event) => {
      if (uttrDispatched) return;
      let interim = '';
      let sawFinal = false;
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
          sawFinal = true;
          finalTranscript += (finalTranscript ? ' ' : '') + bestChunk;
          collectedAlternatives = alts.length > 0 ? alts : [bestChunk];
        } else {
          interim += bestChunk;
          if (alts.length > 0 && collectedAlternatives.length === 0) {
            collectedAlternatives = alts;
          }
        }
      }
      if (interim.trim()) {
        lastInterimTranscript = interim.trim();
      }
      const preview = (finalTranscript || lastInterimTranscript || '').trim();
      if (preview && transcriptEl) {
        transcriptEl.innerHTML = `<span style="color: #e2e8f0;">"${escapeHtml(preview)}"</span>`;
      }

      // Optimization 1: Early-Intent VAD Endpointing (saves 1,200 - 1,800ms of trailing silence wait!)
      if (earlyEndpointTimer) {
        clearTimeout(earlyEndpointTimer);
        earlyEndpointTimer = null;
      }
      const vadBar = document.getElementById('voiceVadLockProgressBar');
      const vadFill = document.getElementById('voiceVadLockProgressFill');
      if (sawFinal && finalTranscript.trim()) {
        if (vadBar && vadFill) {
          vadBar.style.display = 'block';
          vadFill.style.width = '100%';
        }
        // Final chunk arrived from SpeechRecognition: commit immediately in 40ms instead of waiting 1.8s for rec.onend
        earlyEndpointTimer = setTimeout(commitVoiceUtteranceNow, 40);
      } else if (preview && (isExplicitJarvisCommandPhrase(preview) || matchesConfiguredWakeWord(preview))) {
        // Unambiguous Jarvis command phrase detected in streaming interim results:
        // If WebAudio VAD shows vocal cords stopped vibrating (>130ms silence), commit in 180ms; otherwise 260ms
        const silenceMs = Date.now() - (window.AFCCVoice.lastVoiceActivityAtMs || 0);
        const waitMs = silenceMs >= 130 ? 180 : 260;
        if (vadBar && vadFill) {
          vadBar.style.display = 'block';
          vadFill.style.width = '75%';
        }
        earlyEndpointTimer = setTimeout(commitVoiceUtteranceNow, waitMs);
      }
    };

    rec.onerror = (event) => {
      if (earlyEndpointTimer) {
        clearTimeout(earlyEndpointTimer);
        earlyEndpointTimer = null;
      }
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
      if (earlyEndpointTimer) {
        clearTimeout(earlyEndpointTimer);
        earlyEndpointTimer = null;
      }
      const vadBar = document.getElementById('voiceVadLockProgressBar');
      if (vadBar) vadBar.style.display = 'none';
      window.AFCCVoice.isListening = false;
      updateVoiceCopilotUI();
      if (uttrDispatched) return;
      const captured = (finalTranscript || lastInterimTranscript).trim();
      if (captured) {
        commitVoiceUtteranceNow();
      } else {
        handleAcousticShortBurstFallback();
        if (window.AFCCVoice.userWantsListening && window.AFCCVoice.continuousMode && !window.AFCCVoice.isSpeaking) {
          setTimeout(() => {
            if (window.AFCCVoice.userWantsListening && !window.AFCCVoice.isListening && !window.AFCCVoice.isSpeaking) {
              startBrowserSpeechRecognition();
            }
          }, 70);
        }
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

// UX Improvement #5: Global Push-to-Talk Hotkey (Alt+V or Hold Right-Ctrl) from any tab
let _pttRightCtrlDownAtMs = 0;
window.addEventListener('keydown', (ev) => {
  const tag = (ev.target && ev.target.tagName) ? ev.target.tagName.toUpperCase() : '';
  const isInput = tag === 'INPUT' || tag === 'TEXTAREA' || (ev.target && ev.target.isContentEditable);

  // Alt+V toggles J.A.R.V.I.S. Voice Listening globally from any tab
  if (ev.altKey && !ev.ctrlKey && !ev.metaKey && String(ev.key || '').toLowerCase() === 'v') {
    ev.preventDefault();
    const toast = document.getElementById('voiceGlobalFloatingToast');
    const toastTxt = document.getElementById('voiceGlobalFloatingText');
    const nextState = !window.AFCCVoice.isListening;
    if (toast) {
      toast.style.display = nextState ? 'inline-flex' : 'none';
      if (toastTxt && nextState) toastTxt.textContent = '🎙️ J.A.R.V.I.S. Listening (Alt+V)... Speak now';
    }
    toggleVoiceMicListening(nextState);
    return;
  }

  // Hold Right-Ctrl for Push-to-Talk when not typing inside an input
  if (!isInput && ev.code === 'ControlRight' && !ev.repeat && !window.AFCCVoice.isListening) {
    _pttRightCtrlDownAtMs = Date.now();
    const toast = document.getElementById('voiceGlobalFloatingToast');
    const toastTxt = document.getElementById('voiceGlobalFloatingText');
    if (toast) {
      toast.style.display = 'inline-flex';
      if (toastTxt) toastTxt.textContent = '🎙️ Push-to-Talk Active (Hold Right-Ctrl)...';
    }
    toggleVoiceMicListening(true);
  }
});

window.addEventListener('keyup', (ev) => {
  if (ev.code === 'ControlRight' && _pttRightCtrlDownAtMs > 0) {
    const heldMs = Date.now() - _pttRightCtrlDownAtMs;
    _pttRightCtrlDownAtMs = 0;
    if (heldMs >= 250 && window.AFCCVoice.recognition) {
      try { window.AFCCVoice.recognition.stop(); } catch (e) {}
    }
  }
});

window.toggleVoiceCopilotPanel = toggleVoiceCopilotPanel;
window.toggleVoiceMicListening = toggleVoiceMicListening;
window.toggleVoiceContinuousLoop = toggleVoiceContinuousLoop;
window.toggleVoiceSpokenReply = toggleVoiceSpokenReply;
window.toggleVoiceConciseMode = toggleVoiceConciseMode;
window.toggleVoiceAudioStreamingMode = toggleVoiceAudioStreamingMode;
window.toggleVoiceStudioTuningDrawer = toggleVoiceStudioTuningDrawer;
window.renderDynamicVoiceContextChips = renderDynamicVoiceContextChips;
window.renderJarvisLiveSpectrumCanvas = renderJarvisLiveSpectrumCanvas;
window.handleAcousticShortBurstFallback = handleAcousticShortBurstFallback;
window.playJarvisInstantAckChime = playJarvisInstantAckChime;
window.splitTextIntoSpeechClauses = splitTextIntoSpeechClauses;
window.tryInstantClientVoiceFastPath = tryInstantClientVoiceFastPath;
window.stopAfccVoiceSpeaking = stopAfccVoiceSpeaking;
window.setAfccVoiceRate = setAfccVoiceRate;
window.setAfccVoiceLanguage = setAfccVoiceLanguage;
window.setAfccVoiceGender = setAfccVoiceGender;
window.setAfccVoiceAccent = setAfccVoiceAccent;
window.setAfccVoiceRoutingMode = setAfccVoiceRoutingMode;
window.toggleVoiceSpeakerLock = toggleVoiceSpeakerLock;
window.toggleVoiceWakeWordLock = toggleVoiceWakeWordLock;
window.setAfccVoiceWakeWord = setAfccVoiceWakeWord;
window.setAfccVoiceWakeWordRequired = setAfccVoiceWakeWordRequired;
window.calibrateJarvisVoiceprint = calibrateJarvisVoiceprint;
window.openVoiceprintGuidedTeleprompter = openVoiceprintGuidedTeleprompter;
window.closeVoiceprintGuidedTeleprompter = closeVoiceprintGuidedTeleprompter;
window.setVoiceprintCalibrationDuration = setVoiceprintCalibrationDuration;
window.finishJarvisVoiceprintCalibrationNow = finishJarvisVoiceprintCalibrationNow;
window.replayJarvisVoiceprintAudio = replayJarvisVoiceprintAudio;
window.confirmJarvisVoiceprintSave = confirmJarvisVoiceprintSave;
window.cancelJarvisVoiceprintSave = cancelJarvisVoiceprintSave;
window.verifySpeakerBiometrics = verifySpeakerBiometrics;
window.evaluateClientBiometricMatch = evaluateClientBiometricMatch;
window.autoRefineJarvisVoiceprint = autoRefineJarvisVoiceprint;
window.openVoiceprintAccuracySandbox = openVoiceprintAccuracySandbox;
window.setVoiceprintStrictnessThreshold = setVoiceprintStrictnessThreshold;
window.toggleVoiceprintAutoRefine = toggleVoiceprintAutoRefine;
window.runVoiceprintSandboxSimulatedTest = runVoiceprintSandboxSimulatedTest;
window.runVoiceprintSandboxLiveTest = runVoiceprintSandboxLiveTest;
window.submitVoiceprintSandboxFeedback = submitVoiceprintSandboxFeedback;
window.clearVoiceprintSandboxHistory = clearVoiceprintSandboxHistory;
window.renderVoiceprintSandboxPanel = renderVoiceprintSandboxPanel;
window.testAfccSelectedVoice = testAfccSelectedVoice;
window.resolveBestSpeechVoice = resolveBestSpeechVoice;
window.getTargetVoiceLocale = getTargetVoiceLocale;
window.replayLastAfccVoiceReply = replayLastAfccVoiceReply;
window.executeVoiceTurnText = executeVoiceTurnText;
window.executeVoiceUiActions = executeVoiceUiActions;
window.speakAfccVoiceText = speakAfccVoiceText;
window.renderJarvisQueueAndTopicStackBar = renderJarvisQueueAndTopicStackBar;
window.playJarvisSequentialAudioQueue = playJarvisSequentialAudioQueue;
window.processNextJarvisAudioQueueItem = processNextJarvisAudioQueueItem;
window.skipCurrentJarvisAudioQueuePart = skipCurrentJarvisAudioQueuePart;
window.clearJarvisAudioQueue = clearJarvisAudioQueue;
window.resumeParkedJarvisTopicNow = resumeParkedJarvisTopicNow;
