document.addEventListener('DOMContentLoaded', function() {
    const locale = document.body.getAttribute('data-locale') || 'en';
    const t = {
        fa: {
            agendaPlaceholder: 'دستور جلسه را وارد کنید',
            attendeePlaceholder: 'نام شرکت‌کننده را وارد کنید',
            actionDesc: 'توضیح اقدام...',
            assignedTo: 'مسئول...',
            deadline: 'مهلت',
        },
        en: {
            agendaPlaceholder: 'Enter agenda item',
            attendeePlaceholder: 'Enter attendee name',
            actionDesc: 'Action description...',
            assignedTo: 'Assigned to...',
            deadline: 'Deadline',
        }
    };

    /* ===== Theme Switcher (light/dark/auto) ===== */
    (function() {
        const root = document.documentElement;
        const THEME_KEY = 'mm_theme';
        const mql = window.matchMedia('(prefers-color-scheme: dark)');

        function systemPrefersDark() { return mql.matches; }
        function resolveTheme(mode) { return mode === 'auto' ? (systemPrefersDark() ? 'dark' : 'light') : mode; }
        function applyTheme(mode) {
            const effective = resolveTheme(mode);
            root.setAttribute('data-theme', effective === 'dark' ? 'dark' : 'light');
            try { localStorage.setItem(THEME_KEY, mode); } catch(e) {}
            const icon = document.querySelector('.nav-item .material-symbols-rounded');
            if (icon) icon.textContent = effective === 'dark' ? 'dark_mode' : 'light_mode';
        }
        function initTheme() {
            let saved = 'auto';
            try { saved = localStorage.getItem(THEME_KEY) || 'auto'; } catch(e) {}
            applyTheme(saved);
            mql.addEventListener('change', () => {
                let current = 'auto';
                try { current = localStorage.getItem(THEME_KEY) || 'auto'; } catch(e) {}
                if (current === 'auto') applyTheme('auto');
            });
        }
        document.addEventListener('click', (e) => {
            const el = e.target.closest('.theme-select');
            if (!el) return;
            e.preventDefault();
            const selected = el.getAttribute('data-theme');
            applyTheme(selected);
        });
        initTheme();
    })();

    // ===== Drag & Drop sorting for agenda and attendees =====
    if (window.Sortable) {
        const agenda = document.getElementById('agenda-items-container');
        if (agenda) {
            new Sortable(agenda, { animation: 120, handle: '.form-control', ghostClass: 'opacity-50' });
        }
        const attendees = document.getElementById('attendees-container');
        if (attendees) {
            new Sortable(attendees, { animation: 120, handle: '.form-control', ghostClass: 'opacity-50' });
        }
        const actions = document.getElementById('action-items-container');
        if (actions) {
            new Sortable(actions, { animation: 120, handle: '.form-label', ghostClass: 'opacity-50' });
        }
    }

    // ===== Persian Datepicker (jQuery) activation =====
    function initPersianDatepicker() {
        if (typeof $ === 'undefined' || !$.fn || !$.fn.persianDatepicker) return;
        $('[data-jdp]').each(function(){
            const $input = $(this);
            if ($input.data('has-pdp')) return;
            const targetSelector = $input.attr('data-target');
            const $target = targetSelector ? $(targetSelector) : null;
            $input.persianDatepicker({
                format: 'YYYY-MM-DD',
                initialValue: false,
                autoClose: true,
                calendar: { persian: { locale: 'fa' } },
                toolbox: { calendarSwitch: { enabled: false } },
                onSelect: function(unix){
                    try {
                        var p = new persianDate(unix).format('YYYY-MM-DD'); // نمایش شمسی
                        var g = new persianDate(unix).toCalendar('gregorian').format('YYYY-MM-DD'); // مقدار میلادی برای بک‌اند
                        $input.val(p).trigger('input').trigger('change');
                        if ($target && $target.length) { $target.val(g); }
                        $input.attr('data-greg', g);
                    } catch(e) {}
                }
            });
            $input.attr('autocomplete', 'off');
            $input.data('has-pdp', true);
        });
    }
    initPersianDatepicker();
    // Native date input is default now; keep helper for older browsers
    function openNativePickerFallback(input){ try { if (input && typeof input.showPicker==='function') input.showPicker(); } catch(e) {} }
    // Open Persian datepicker if available, otherwise fallback to native
    function openPickerFor(input){ openNativePickerFallback(input); }
    // Remove JDP bindings; use native type=date

    // Calendar buttons open the adjacent input's datepicker
    document.body.addEventListener('click', function(e){
        const btn = e.target.closest('.jdp-open');
        if (!btn) return;
        e.preventDefault();
        const input = btn.parentElement && btn.parentElement.querySelector('[data-jdp]');
        if (input) {
            openPickerFor(input);
            setTimeout(() => input.focus(), 0);
        }
    });

    // Company Other -> show uploader
    const companySelect = document.getElementById('companySelect');
    const uploader = document.getElementById('customLogoUploader');
    const customNameBox = document.getElementById('customCompanyName');
    function syncUploader(){
        if (!companySelect || !uploader) return;
        const val = companySelect.value || '';
        const show = (val === 'Other' || val === 'شرکت دیگر');
        uploader.style.display = show ? 'block' : 'none';
        if (customNameBox) customNameBox.style.display = show ? 'block' : 'none';
    }
    if (companySelect){
        companySelect.addEventListener('change', syncUploader);
        setTimeout(syncUploader, 0);
    }

    const addAgendaItemButton = document.getElementById('add-agenda-item');
    const agendaItemsContainer = document.getElementById('agenda-items-container');
    if (addAgendaItemButton && agendaItemsContainer) {
        addAgendaItemButton.addEventListener('click', function() {
            const currentItemCount = agendaItemsContainer.children.length;
            const newItemDiv = document.createElement('div');
            newItemDiv.classList.add('agenda-item', 'input-group', 'mb-1');
            const newInput = document.createElement('input');
            newInput.type = 'text';
            newInput.name = `agenda_items-${currentItemCount}`;
            newInput.id = `agenda_items-${currentItemCount}`;
            newInput.classList.add('form-control');
            newInput.placeholder = (locale==='fa'? t.fa.agendaPlaceholder : t.en.agendaPlaceholder);
            newInput.setAttribute('autocomplete','off');

            const removeButton = document.createElement('button');
            removeButton.type = 'button';
            removeButton.innerHTML = '<i class="bi bi-trash3-fill"></i>';
            removeButton.classList.add('btn', 'btn-outline-danger', 'btn-sm', 'remove-agenda-item');

            newItemDiv.appendChild(newInput);
            newItemDiv.appendChild(removeButton);
            agendaItemsContainer.appendChild(newItemDiv);
        });
        agendaItemsContainer.addEventListener('click', function(event) {
            if (event.target.closest('.remove-agenda-item')) {
                const itemToRemove = event.target.closest('.agenda-item');
                if (itemToRemove) { itemToRemove.remove(); }
            }
        });
    }

    const addAttendeeButton = document.getElementById('add-attendee-button');
    const attendeesContainer = document.getElementById('attendees-container');
    if (addAttendeeButton && attendeesContainer) {
        addAttendeeButton.addEventListener('click', function() {
            const currentItemCount = attendeesContainer.children.length;
            const newItemDiv = document.createElement('div');
            newItemDiv.classList.add('attendee-item', 'input-group', 'mb-1');
            const newInput = document.createElement('input');
            newInput.type = 'text';
            newInput.name = `attendees-${currentItemCount}`;
            newInput.id = `attendees-${currentItemCount}`;
            newInput.classList.add('form-control');
            newInput.placeholder = (locale==='fa'? t.fa.attendeePlaceholder : t.en.attendeePlaceholder);
            newInput.setAttribute('autocomplete','off');

            const removeButton = document.createElement('button');
            removeButton.type = 'button';
            removeButton.innerHTML = '<i class="bi bi-trash3-fill"></i>';
            removeButton.classList.add('btn', 'btn-outline-danger', 'btn-sm', 'remove-attendee-item');

            newItemDiv.appendChild(newInput);
            newItemDiv.appendChild(removeButton);
            attendeesContainer.appendChild(newItemDiv);
        });
        attendeesContainer.addEventListener('click', function(event) {
            if (event.target.closest('.remove-attendee-item')) {
                const itemToRemove = event.target.closest('.attendee-item');
                if (itemToRemove) { itemToRemove.remove(); }
            }
        });
    }

    const addActionButton = document.getElementById('add-action-item-button');
    const actionItemsContainer = document.getElementById('action-items-container');
    function collectAttendees(){
        const list = [];
        const wrap = document.getElementById('attendees-container');
        if (!wrap) return list;
        wrap.querySelectorAll('input[name^="attendees-"]').forEach(inp => {
            const v = (inp.value || '').trim();
            if (v) list.push(v);
        });
        return list;
    }
    function populateAssigneeSelect(selectEl){
        const current = selectEl.getAttribute('data-current') || '';
        const attendees = collectAttendees();
        const val = selectEl.value;
        selectEl.innerHTML = '';
        const opt0 = document.createElement('option'); opt0.value=''; opt0.textContent = (document.body.getAttribute('data-locale')==='fa' ? 'انتخاب کنید' : 'Select');
        selectEl.appendChild(opt0);
        attendees.forEach(name => {
            const opt = document.createElement('option');
            opt.value = name; opt.textContent = name;
            selectEl.appendChild(opt);
        });
        const toSet = current || val;
        if (toSet) selectEl.value = toSet;
    }
    function refreshAllAssigneeSelects(){
        document.querySelectorAll('select.assignee-select').forEach(populateAssigneeSelect);
    }
    if (addActionButton && actionItemsContainer) {
        addActionButton.addEventListener('click', function() {
            const currentItemCount = actionItemsContainer.children.length;
            const newItemDiv = document.createElement('div');
            newItemDiv.classList.add('action-item-group', 'border', 'p-3', 'mb-3', 'rounded');

            const descDiv = document.createElement('div');
            descDiv.classList.add('mb-2');
            const descLabel = document.createElement('label');
            descLabel.setAttribute('for', `action_items-${currentItemCount}-description`);
            descLabel.textContent = (locale==='fa'? 'توضیح' : 'Description');
            descLabel.classList.add('form-label');

            const descInput = document.createElement('textarea');
            descInput.name = `action_items-${currentItemCount}-description`;
            descInput.id = `action_items-${currentItemCount}-description`;
            descInput.rows = 2;
            descInput.classList.add('form-control');
            descInput.placeholder = (locale==='fa'? t.fa.actionDesc : t.en.actionDesc);

            descDiv.appendChild(descLabel);
            descDiv.appendChild(descInput);
            newItemDiv.appendChild(descDiv);

            const fieldRowDiv = document.createElement('div');
            fieldRowDiv.classList.add('row', 'g-2', 'align-items-end');

            const assignedDiv = document.createElement('div');
            assignedDiv.classList.add('col-md-5');
            const assignedLabel = document.createElement('label');
            assignedLabel.setAttribute('for', `action_items-${currentItemCount}-assigned_to`);
            assignedLabel.textContent = (locale==='fa'? 'مسئول' : 'Assigned To');
            assignedLabel.classList.add('form-label');

            const assignedSelect = document.createElement('select');
            assignedSelect.name = `action_items-${currentItemCount}-assigned_to`;
            assignedSelect.id = `action_items-${currentItemCount}-assigned_to`;
            assignedSelect.className = 'form-select assignee-select';
            assignedSelect.setAttribute('data-current','');

            assignedDiv.appendChild(assignedLabel);
            assignedDiv.appendChild(assignedSelect);
            fieldRowDiv.appendChild(assignedDiv);

            const deadlineDiv = document.createElement('div');
            deadlineDiv.classList.add('col-md-5');
            const deadlineLabel = document.createElement('label');
            deadlineLabel.setAttribute('for', `action_items-${currentItemCount}-deadline`);
            deadlineLabel.textContent = (locale==='fa'? t.fa.deadline : t.en.deadline);
            deadlineLabel.classList.add('form-label');

            const deadlineInput = document.createElement('input');
            deadlineInput.type = 'date';
            deadlineInput.name = `action_items-${currentItemCount}-deadline`;
            deadlineInput.id = `action_items-${currentItemCount}-deadline`;
            deadlineInput.classList.add('form-control');
            deadlineInput.setAttribute('autocomplete','off');
            // Wrap input and add calendar button similar to meeting_date
            const ig = document.createElement('div');
            ig.className = 'input-group';
            ig.appendChild(deadlineInput);
            const openBtn = document.createElement('button');
            openBtn.type = 'button';
            openBtn.className = 'btn btn-outline-secondary rounded-3';
            openBtn.innerHTML = '<i class="bi bi-calendar-event"></i>';
            openBtn.addEventListener('click', function(){
                if (typeof deadlineInput.showPicker === 'function') { try { deadlineInput.showPicker(); } catch(e) {} }
                else { deadlineInput.focus(); }
            });
            ig.appendChild(openBtn);

            deadlineDiv.appendChild(deadlineLabel);
            deadlineDiv.appendChild(ig);
            fieldRowDiv.appendChild(deadlineDiv);

            const removeButtonDiv = document.createElement('div');
            removeButtonDiv.classList.add('col-md-2');
            const removeButton = document.createElement('button');
            removeButton.type = 'button';
            removeButton.innerHTML = '<i class="bi bi-trash3-fill"></i>';
            removeButton.classList.add('btn', 'btn-danger', 'btn-sm', 'w-100', 'remove-action-item');
            removeButtonDiv.appendChild(removeButton);
            fieldRowDiv.appendChild(removeButtonDiv);

            newItemDiv.appendChild(fieldRowDiv);
            actionItemsContainer.appendChild(newItemDiv);

            // init Persian datepicker for the new input & populate assignee select
            initPersianDatepicker();
            refreshAllAssigneeSelects();
        });

        // Before form submit, replace Persian-picked values with Gregorian for backend
        // دیگر نیازی به دستکاری name قبل از ارسال نیست، چون مقدار میلادی در hidden target می‌رود

        actionItemsContainer.addEventListener('click', function(event) {
            if (event.target.closest('.remove-action-item')) {
                const itemToRemove = event.target.closest('.action-item-group');
                if (itemToRemove) { itemToRemove.remove(); }
            }
        });
    }

    // Keep assignee options synced when attendees change
    if (attendeesContainer) {
        attendeesContainer.addEventListener('input', function(e){ if (e.target && e.target.name && e.target.name.startsWith('attendees-')) refreshAllAssigneeSelects(); });
        attendeesContainer.addEventListener('click', function(e){ if (e.target.closest('.remove-attendee-item')) setTimeout(refreshAllAssigneeSelects, 0); });
    }

    // First load
    refreshAllAssigneeSelects();

  // Mark app as ready (hide skeleton overlays)
  try { document.body.classList.add('app-ready'); } catch(e) {}
}); // End of DOMContentLoaded listener