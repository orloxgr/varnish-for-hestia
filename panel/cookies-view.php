<?php
require $root . '/web/templates/header.php';
$panel = top_panel($headerOwner, $TAB);
$cookieDomain = $data['domain'] ?? $request['domain'] ?? null;
$centralCookies = ($data['cookie_scope'] ?? '') === 'central';
$back = $centralCookies ? './' : '?owner=' . rawurlencode($owner) . '&domain=' . rawurlencode((string)$cookieDomain);
$choices = $data['cookie_policies'] ?? ['schemaVersion' => 1, 'rules' => []];
?>
<style>
.cookie-toolbar{display:flex;flex-wrap:wrap;gap:12px;align-items:end;margin:18px 0}.cookie-toolbar label{display:grid;gap:5px}.cookie-toolbar input,.cookie-toolbar select{min-width:150px}.cookie-sheet{overflow:auto;border:1px solid #80808066;border-radius:6px}.cookie-sheet table{width:100%;border-collapse:collapse}.cookie-sheet th,.cookie-sheet td{padding:10px;vertical-align:top;border-bottom:1px solid #80808055;text-align:left}.cookie-sheet th{position:sticky;top:0;background:#444;color:#fff;z-index:1}.cookie-sheet input[type=text]{min-width:210px}.cookie-sheet textarea{min-width:260px;resize:vertical}.cookie-sheet select{min-width:190px}.cookie-sheet small{display:block;max-width:360px;margin-top:6px;overflow-wrap:anywhere}.cookie-sheet code{font-size:11px;overflow-wrap:anywhere}.cookie-sheet tr[data-dirty=true]{box-shadow:inset 3px 0 #727cf5}.cookie-message{min-height:1.5em}.cookie-paste{width:100%;box-sizing:border-box}.cookie-sheet details{margin-top:8px}.cookie-sheet summary{cursor:pointer}.cookie-actions{white-space:nowrap}
</style>
<div class="toolbar"><div class="toolbar-inner"><div class="toolbar-buttons">
<a class="button button-secondary" href="<?= $escape($back) ?>" title="Return to cache management. Unsaved cookie edits stay on this page only.">← Back</a>
<button class="button" type="submit" form="cookie-form" title="Validate, compile and activate these choices. Only websites whose executable policy changed are invalidated.">Save &amp; apply</button>
</div></div></div>
<div class="container"><div class="form-container form-container-wide">
<h1 class="u-mb10">Cookie cache policies</h1>
<p class="u-mb10"><strong><?= $centralCookies ? 'All websites · central choices' : $escape($cookieDomain) ?></strong><?= $centralCookies ? ' · Website overrides take precedence.' : ' · Only this website and its aliases.' ?></p>
<?php if ($pageError !== ''): ?><div class="alert alert-danger u-mb20" role="alert"><p><?= $escape($pageError) ?> The previous policy remains active.</p></div>
<?php elseif (!empty($data['cookie_policy_saved'])): ?><div class="alert alert-success u-mb20" role="status"><p>Cookie policies were compiled and applied.</p></div><?php endif; ?>
<p class="u-mb10">Cookies stay in the browser and reach the application. <strong>Shared HTML</strong> removes their value from Cookie variation; <strong>Public variant</strong> adds their value to the cache key; <strong>Private</strong> sends matching requests to the application. <strong>Automatic</strong> uses the existing policy.</p>
<p class="u-mb10">Login, cart/session contracts and origin private/no-store decisions remain authoritative. Recognition descriptions and inferred suggestions do not automatically enable policies. Cookie issuance and consent use the existing provider integrations.</p>
<?php if (($data['cookie_profile'] ?? '') === 'basic'): ?><p class="u-mb10">Basic works without the WordPress plugin. Personal fragments require an actual application integration.</p><?php endif; ?>
<form id="cookie-form" method="post">
<?php $formFields($centralCookies ? 'admin-cookie-policies-save' : 'configure-cookie-policies', $cookieDomain); ?>
<input type="hidden" name="cookie_policies" id="cookie-payload">
<?php if (!$centralCookies): $integration = $data['cookie_integration'] ?? ['enabled' => false, 'url' => 'https://' . $cookieDomain . '/wp-json/ultracache/v1/cookie-policy-control']; ?>
<?php if (!empty($data['cookie_integration_notice'])): ?><p class="u-mb10" role="status"><?= $escape($data['cookie_integration_notice']) ?></p><?php endif; ?>
<details class="box-collapse u-mb20"><summary class="box-collapse-header" title="Connect an installed, compatible UltraCache WordPress integration explicitly. Basic needs no WordPress plugin.">WordPress integration · <?= !empty($integration['enabled']) ? 'Connected' : 'Not connected' ?></summary><div class="box-collapse-content">
<label class="form-label u-block u-mb10"><input type="checkbox" name="cookie_integration_enabled" value="1" <?= !empty($integration['enabled']) ? 'checked' : '' ?> title="Save & apply authenticates the configured endpoint and synchronizes these choices with the application’s supported engines. Requires a compatible UltraCache WordPress version and matching site token."> Synchronize policies with UltraCache WordPress</label>
<label class="form-label u-block u-mb10" for="cookie-integration-url">WordPress control endpoint</label><input class="form-control" id="cookie-integration-url" name="cookie_integration_url" value="<?= $escape($integration['url']) ?>" title="The exact control endpoint on this website or a native owned alias. Redirects and other websites are refused. The existing configured site token authenticates requests and responses.">
<p class="u-mt10">Enable only after installing the compatible WordPress integration and configuring the same site token. Save applies the snapshot to PHP/drop-in/Apache Static capabilities reported by that integration. Disabling clears the managed application snapshot before disconnecting; a failed operation retains the previous configuration. No websites are scanned.</p>
</div></details>
<?php endif; ?>
<div class="cookie-toolbar">
<label>Search<input class="form-control" id="cookie-search" type="search" placeholder="Name, description or provider" title="Search every local recognition record, reviewed policy and custom row."></label>
<label>Action<select class="form-select" id="cookie-action-filter" title="Filter by the currently displayed cache action."><option value="">All actions</option><option value="automatic">Automatic</option><option value="shared">Shared HTML</option><option value="variant">Public variant</option><option value="private">Private</option></select></label>
<label>Source<select class="form-select" id="cookie-source-filter" title="Show inherited, locally overridden or custom entries."><option value="">All entries</option><option value="local">Local choices</option><option value="inherited">Inherited/default</option><option value="custom">Custom rows</option></select></label>
<label>Rows per page<select class="form-select" id="cookie-page-size" title="Pagination changes display only. All records remain searchable and selectable."><option>25</option><option selected>100</option><option value="all">All</option></select></label>
</div>
<div class="cookie-toolbar">
<button type="button" class="button button-secondary" id="cookie-add" title="Add a custom cookie with a stable automatically generated ID. Use a trailing * for a literal prefix.">Add cookie</button>
<label>Selected rows<select class="form-select" id="cookie-bulk-action" title="Choose a cache action to apply to selected rows when you click Apply to selected."><option value="automatic">Automatic</option><option value="shared">Shared HTML</option><option value="variant">Public variant</option><option value="private">Private</option></select></label>
<button type="button" class="button button-secondary" id="cookie-bulk" title="Set the chosen action on selected rows. Changes take effect only after Save & apply.">Apply to selected</button>
<button type="button" class="button button-secondary" id="cookie-suggest" title="Copy each selected row’s displayed proposal into a local choice. Inferred proposals are estimates; inspect the row’s reason first.">Use proposals</button>
<button type="button" class="button button-secondary" id="cookie-reset" title="Remove local choices from selected rows and inherit the central/reviewed policy again. Selected custom rows are removed.">Reset selected</button>
</div>
<p id="cookie-count" class="cookie-message" aria-live="polite"></p>
<div class="cookie-sheet"><table aria-label="Cookie cache policies"><thead><tr>
<th><input type="checkbox" id="cookie-select-page" aria-label="Select visible rows" title="Select or deselect the rows displayed on this page."></th><th>ID</th><th>Cookie</th><th>Description</th><th>Cache action</th><th>Proposal / source</th>
</tr></thead><tbody id="cookie-rows"></tbody></table></div>
<div class="cookie-toolbar"><button type="button" class="button button-secondary" id="cookie-prev" title="Display the previous page of matching rows.">← Previous</button><span id="cookie-page"></span><button type="button" class="button button-secondary" id="cookie-next" title="Display the next page of matching rows.">Next →</button></div>
<details class="box-collapse u-mb20"><summary class="box-collapse-header" title="Paste tab-separated rows copied from Excel. IDs are created automatically.">Paste rows from Excel</summary><div class="box-collapse-content">
<p class="u-mb10">Columns: cookie name, description, action (automatic/shared/variant/private). One cookie per line; a trailing * means prefix. A spreadsheet header row is optional.</p>
<textarea id="cookie-paste" class="form-control cookie-paste" rows="5" spellcheck="false" title="Paste tab-separated cookie, description and optional action columns. Existing rows are not overwritten."></textarea>
<button type="button" class="button button-secondary u-mt10" id="cookie-import" title="Append every pasted row as a custom cookie. Nothing is applied until Save & apply.">Append pasted rows</button>
</div></details>
<p id="cookie-error" class="cookie-message" role="alert"></p>
</form></div></div>
<script type="application/json" id="cookie-initial"><?= json_encode(['rows' => $data['cookie_policy_rows'] ?? [], 'settings' => $choices, 'scope' => $data['cookie_scope'] ?? 'site'], JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT | JSON_THROW_ON_ERROR) ?></script>
<script>
(() => {
'use strict';
const initial=JSON.parse(document.getElementById('cookie-initial').textContent);
const $=id=>document.getElementById(id), actions={automatic:'Automatic',shared:'Shared HTML',variant:'Public variant',private:'Private'};
const rows=new Map(initial.rows.map(r=>[r.id,r])), choices=new Map(initial.settings.rules.map(r=>[r.id,r])), selected=new Set();
let page=0,dirty=false,visible=[];
function current(row){return choices.get(row.id)?.action ?? row.inherited_action ?? row.action;}
function parseName(value){const prefix=value.endsWith('*');return {kind:prefix?'prefix':'exact',value:prefix?value.slice(0,-1):value};}
function snapshot(row){return choices.get(row.id) ?? {id:row.id,match:{...row.match},description:row.description,action:current(row)};}
function edit(row,field,value){const rule={...snapshot(row),match:{...snapshot(row).match}};rule[field]=value;choices.set(row.id,rule);dirty=true;$('cookie-count').textContent=filtered().length+' matching / '+rows.size+' cookies · '+selected.size+' selected · '+choices.size+' local choices · Unsaved changes';}
function filtered(){const query=$('cookie-search').value.toLocaleLowerCase(),action=$('cookie-action-filter').value,source=$('cookie-source-filter').value;
return [...rows.values()].filter(row=>{const rule=choices.get(row.id),name=rule?rule.match.value+(rule.match.kind==='prefix'?'*':''):row.name;return (!query||[name,rule?.description??row.description,row.provider,row.id].join(' ').toLocaleLowerCase().includes(query))&&(!action||current(row)===action)&&(!source||(source==='local'?!!rule:source==='custom'?row.id.startsWith('custom:'):!rule));});}
function element(tag,text){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;return node;}
function render(){const found=filtered(),size=$('cookie-page-size').value==='all'?Math.max(found.length,1):Number($('cookie-page-size').value),pages=Math.max(1,Math.ceil(found.length/size));page=Math.max(0,Math.min(page,pages-1));visible=found.slice(page*size,(page+1)*size);const body=$('cookie-rows');body.replaceChildren();
for(const row of visible){const rule=choices.get(row.id),tr=element('tr');tr.dataset.dirty=String(!!rule);let td=element('td'),check=element('input');check.type='checkbox';check.checked=selected.has(row.id);check.title='Select this cookie for a bulk action.';check.setAttribute('aria-label','Select '+row.name);check.onchange=()=>{check.checked?selected.add(row.id):selected.delete(row.id);counts(found.length,pages);};td.append(check);tr.append(td);
td=element('td');td.append(element('code',row.id));tr.append(td);
td=element('td');const name=element('input');name.type='text';name.className='form-control';name.value=rule?rule.match.value+(rule.match.kind==='prefix'?'*':''):row.name;name.title='Case-sensitive literal cookie name. Use a trailing * for a prefix; other regex syntax is literal.';name.oninput=()=>edit(row,'match',parseName(name.value.trim()));td.append(name);tr.append(td);
td=element('td');const description=element('textarea');description.rows=2;description.className='form-control';description.value=rule?.description??row.description;description.title='Description saved only in this scope. Upstream updates do not overwrite your choice.';description.oninput=()=>edit(row,'description',description.value);td.append(description);td.append(element('small',row.provider||'Custom / unspecified provider'));tr.append(td);
td=element('td');const action=element('select');action.className='form-select';action.title='Controls actual cache handling after Save & apply. Origin privacy and core authentication/session rules still take precedence.';for(const [value,label] of Object.entries(actions)){const option=element('option',label);option.value=value;option.selected=value===current(row);action.append(option);}action.onchange=()=>{edit(row,'action',action.value);render();};td.append(action);td.append(element('small',rule?'Local choice · '+initial.scope:'Inherited · '+(row.inherited_scope??row.scope)));tr.append(td);
td=element('td');td.append(element('strong',actions[row.proposal]??'Automatic'));td.append(element('small',row.confidence+' · '+row.htmlEffect));const details=element('details'),summary=element('summary','Why / precedence');summary.title='Show the reason, evidence and rules that can take precedence.';details.append(summary,element('small',row.reason),element('small',row.core_precedence));for(const source of row.sources??[])details.append(element('small',typeof source==='string'?source:JSON.stringify(source)));td.append(details);tr.append(td);body.append(tr);}
$('cookie-select-page').checked=visible.length>0&&visible.every(row=>selected.has(row.id));$('cookie-prev').disabled=page===0;$('cookie-next').disabled=page+1>=pages;counts(found.length,pages);}
function counts(total,pages){$('cookie-count').textContent=total+' matching / '+rows.size+' cookies · '+selected.size+' selected · '+choices.size+' local choices'+(dirty?' · Unsaved changes':'');$('cookie-page').textContent='Page '+(page+1)+' / '+pages;}
function add(name='',description='',action='automatic'){const id='custom:'+crypto.randomUUID(),match=parseName(name);const row={id,name,match,description,provider:'',category:'Custom',proposal:'automatic',action,scope:initial.scope,confidence:'user-choice',htmlEffect:'site-dependent',reason:'Custom local choice.',sources:[],core_precedence:'Core authentication/session and origin privacy rules remain authoritative.'};rows.set(id,row);choices.set(id,{id,match,description,action});dirty=true;return row;}
for(const id of ['cookie-search','cookie-action-filter','cookie-source-filter','cookie-page-size'])$(id).addEventListener('input',()=>{page=0;render();});
for(const field of document.querySelectorAll('[name=cookie_integration_enabled],[name=cookie_integration_url]'))field.addEventListener('input',()=>{dirty=true;$('cookie-error').textContent='WordPress integration has unsaved changes.';});
$('cookie-select-page').onchange=event=>{for(const row of visible)event.target.checked?selected.add(row.id):selected.delete(row.id);render();};
$('cookie-add').onclick=()=>{add();$('cookie-search').value='';$('cookie-source-filter').value='local';$('cookie-action-filter').value='';page=Math.floor((filtered().length-1)/(Number($('cookie-page-size').value)||Math.max(filtered().length,1)));render();};
$('cookie-bulk').onclick=()=>{for(const id of selected){const row=rows.get(id);if(row)edit(row,'action',$('cookie-bulk-action').value);}render();};
$('cookie-suggest').onclick=()=>{for(const id of selected){const row=rows.get(id);if(row)edit(row,'action',row.proposal);}render();};
$('cookie-reset').onclick=()=>{for(const id of selected){choices.delete(id);const row=rows.get(id);if(id.startsWith('custom:')&&!row?.inherited_exists){rows.delete(id);}else if(row?.reset_match){Object.assign(row,{match:{...row.reset_match},name:row.reset_name,description:row.reset_description},row.reset_metadata??{proposal:row.reset_proposal,provider:row.reset_provider});}}selected.clear();dirty=true;render();};
$('cookie-prev').onclick=()=>{page--;render();};$('cookie-next').onclick=()=>{page++;render();};
$('cookie-import').onclick=()=>{const lines=$('cookie-paste').value.replace(/\r/g,'').split('\n').filter(line=>line.trim());let imported=0;for(const [i,line] of lines.entries()){const [name,description='',rawAction='automatic']=line.split('\t');if(i===0&&/^(cookie|cookie name)$/i.test(name.trim()))continue;const action=rawAction.trim().toLowerCase();if(!Object.hasOwn(actions,action)){ $('cookie-error').textContent='Unknown action on pasted row '+(i+1)+'. Use automatic, shared, variant or private.';return;}imported++;}for(const [i,line] of lines.entries()){const [name,description='',rawAction='automatic']=line.split('\t');if(i===0&&/^(cookie|cookie name)$/i.test(name.trim()))continue;add(name.trim(),description,rawAction.trim().toLowerCase());}$('cookie-paste').value='';$('cookie-error').textContent=imported+' rows appended. Save & apply to activate them.';$('cookie-source-filter').value='local';$('cookie-search').value='';page=0;render();};
$('cookie-form').onsubmit=event=>{const rules=[...choices.values()];for(const rule of rules){if(!/^[!#$%&'*+.^_`|~0-9A-Za-z-]+$/.test(rule.match.value)){event.preventDefault();$('cookie-error').textContent='Use a valid cookie name or trailing-star prefix: '+rule.id;return;}}$('cookie-payload').value=JSON.stringify({schemaVersion:1,rules});dirty=false;};
window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});render();
})();
</script>
<?php require $root . '/web/templates/footer.php'; ?>
