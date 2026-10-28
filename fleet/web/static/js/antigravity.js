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
      input.value = cmd;
      input.focus();
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
    }, 500);

    // --- Model Selector & Usage Details ---
    async function fetchModels() {
      try {
        const res = await fetch('/api/antigravity/models');
        const data = await res.json();
        availableModels = data.models || [];
        activeModelId = data.active_model || 'gemini-3.8-flash-high';
        
        const activeObj = availableModels.find(m => m.id === activeModelId) || availableModels[0];
        const labelText = activeObj ? `${activeObj.name} ${activeObj.effort || ''}`.trim() : 'Gemini 3.8 Flash High';
        const labelEl = document.getElementById('agActiveModelLabel');
        if (labelEl) labelEl.innerText = labelText;

        const list = document.getElementById('agModelOptionsList');
        if (list) {
          list.innerHTML = availableModels.map(m => {
            const isSelected = m.id === activeModelId;
            const isDis = !m.available;
            const check = isSelected ? '<span style="color:var(--accent-cyan); font-weight:bold; margin-right:6px;">✓</span>' : '<span style="display:inline-block; width:14px; margin-right:6px;"></span>';
            const badgeClass = m.badge_color || 'gray';
            return `
              <div class="ag-model-menu-item ${isSelected ? 'active' : ''} ${isDis ? 'disabled' : ''}" onclick="selectModel('${m.id}', ${isDis ? 'true' : 'false'})">
                <div style="display:flex; align-items:center;">
                  ${check}
                  <span>${escapeHtml(m.name)}</span>
                </div>
                <div>
                  <span class="ag-pill-badge ${badgeClass}">${escapeHtml(m.badge || m.effort || '')}</span>
                </div>
              </div>
            `;
          }).join('');
        }
      } catch (e) {
        console.error('Error fetching models:', e);
      }
    }

    function toggleModelMenu(e) {
      if (e) e.stopPropagation();
      const menu = document.getElementById('agModelMenu');
      if (!menu) return;
      menu.style.display = menu.style.display === 'block' ? 'none' : 'block';
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

    function toggleAntigravityRightDock(forceState) {
      const nextState = (typeof forceState === 'boolean') ? forceState : !window.isAgRightDocked;
      const viewAg = document.getElementById('viewAntigravity');
      const dockSlot = document.getElementById('agRightDockSlot');
      const mainAnchor = document.getElementById('agMainStageAnchor');
      const btnToggle = document.getElementById('btnToggleAgRightDock');
      const btnClose = document.getElementById('btnCloseAgRightDock');
      const btnHeader = document.getElementById('btnHeaderRightDockChat');
      const btnGlobalHeader = document.getElementById('btnGlobalHeaderRightDock');

      if (!viewAg || !dockSlot) return;
      window.isAgRightDocked = nextState;
      try {
        localStorage.setItem('fleet_ag_right_docked', nextState ? '1' : '0');
      } catch (e) {}

      if (nextState) {
        dockSlot.appendChild(viewAg);
        dockSlot.style.display = 'flex';
        viewAg.style.display = 'flex';
        viewAg.classList.add('ag-docked-right');

        if (btnToggle) {
          btnToggle.innerHTML = '⤢ Full Page';
          btnToggle.title = 'Expand chatbot back to full page tab';
        }
        if (btnClose) btnClose.style.display = 'inline-flex';
        if (btnHeader) {
          btnHeader.innerHTML = '◨ Undock Chat';
          btnHeader.style.background = 'rgba(0, 242, 254, 0.2)';
        }
        if (btnGlobalHeader) {
          btnGlobalHeader.innerHTML = '◨ Hide Right Chat';
          btnGlobalHeader.style.background = 'rgba(16, 185, 129, 0.2)';
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

        // If user was on the full-page antigravity tab, switch the left main stage to their previous agent tab so they can browse side-by-side!
        if (typeof currentTab !== 'undefined' && currentTab === 'antigravity') {
          const targetTab = (window.lastNonAgTab && window.lastNonAgTab !== 'antigravity') ? window.lastNonAgTab : 'overview';
          if (typeof FleetNavigator !== 'undefined' && typeof FleetNavigator.switchAgent === 'function') {
            FleetNavigator.switchAgent(targetTab);
          } else if (typeof switchTab === 'function') {
            switchTab(targetTab);
          }
        }
      } else {
        if (mainAnchor && mainAnchor.parentNode) {
          mainAnchor.parentNode.insertBefore(viewAg, mainAnchor.nextSibling);
        }
        dockSlot.style.display = 'none';
        viewAg.classList.remove('ag-docked-right');

        if (btnToggle) {
          btnToggle.innerHTML = '◨ Dock to Right Panel';
          btnToggle.title = 'Dock chatbot to the right panel so you can browse other agent pages while chatting';
        }
        if (btnClose) btnClose.style.display = 'none';
        if (btnHeader) {
          btnHeader.innerHTML = '◨ Dock Chat Panel';
          btnHeader.style.background = 'rgba(16, 185, 129, 0.12)';
        }
        if (btnGlobalHeader) {
          btnGlobalHeader.innerHTML = '◨ Right Chat';
          btnGlobalHeader.style.background = 'rgba(0, 242, 254, 0.08)';
          btnGlobalHeader.style.color = 'var(--accent-cyan)';
        }
        if (typeof switchTab === 'function') {
          switchTab('antigravity');
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
      if (btnToggle) btnToggle.innerHTML = '◨ Dock to Right Panel';
      if (btnClose) btnClose.style.display = 'none';
      if (btnHeader) btnHeader.innerHTML = '◨ Dock Chat Panel';
      if (btnGlobalHeader) {
        btnGlobalHeader.innerHTML = '◨ Right Chat';
        btnGlobalHeader.style.background = 'rgba(0, 242, 254, 0.08)';
        btnGlobalHeader.style.color = 'var(--accent-cyan)';
      }
    }

    function dockFleetChatToRightPanel() {
      toggleAntigravityRightDock(true);
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
window.toggleAntigravityRightDock = toggleAntigravityRightDock;
window.closeAntigravityRightDock = closeAntigravityRightDock;
window.dockFleetChatToRightPanel = dockFleetChatToRightPanel;
