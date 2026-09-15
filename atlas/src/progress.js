/* Offline tracked-layer status. Imported reports stay separate from local overrides. */
(function () {
  'use strict';
  const STORAGE_KEY = 'tauceti-explorer-progress-v1';
  const MAX_BYTES = 2 * 1024 * 1024;
  const MAX_NOTE = 4000;
  const STATUSES = new Set(['planned', 'in_progress', 'complete', 'unknown']);
  const own = (object, key) => Object.prototype.hasOwnProperty.call(object, key);
  const plainObject = object => !!object && typeof object === 'object' && !Array.isArray(object) && (Object.getPrototypeOf(object) === Object.prototype || Object.getPrototypeOf(object) === null);
  const percentFor = status => status === 'complete' ? 100 : status === 'in_progress' ? 50 : 0;
  const now = () => new Date().toISOString();
  const validDate = value => typeof value === 'string' && value.length <= 64 && Number.isFinite(Date.parse(value));

  class TauProgress {
    constructor(data, overlay) {
      this.data = data || {};
      this.overlay = overlay || {};
      this.stages = new Map((this.data.stages || []).map(stage => [stage.id, stage]));
      this.roadmaps = new Map((this.data.roadmaps || []).map(roadmap => [roadmap.id, roadmap]));
      this.groups = new Map((this.data.groups || []).map(group => [group.id, group]));
      this.children = new Map(Array.from(this.stages.keys(), id => [id, []]));
      this.roadmapChildren = new Map(Array.from(this.roadmaps.keys(), id => [id, []]));
      this.byOwner = new Map(Array.from(this.roadmaps.keys(), id => [id, []]));
      this.stages.forEach(stage => {
        // A source refinement is planning detail beneath its layer, not a tracked
        // target: it never enters the leaf counts and never inherits a status.
        if (stage.expansion) return;
        if (stage.parentStageId && this.children.has(stage.parentStageId) && stage.parentStageId !== stage.id) this.children.get(stage.parentStageId).push(stage.id);
        if (this.byOwner.has(stage.owner)) this.byOwner.get(stage.owner).push(stage.id);
      });
      this.roadmaps.forEach(roadmap => {
        if (roadmap.parentRoadmapId && this.roadmapChildren.has(roadmap.parentRoadmapId) && roadmap.parentRoadmapId !== roadmap.id) this.roadmapChildren.get(roadmap.parentRoadmapId).push(roadmap.id);
      });
      this.manual = new Map();
      this.listeners = new Set();
      this.updatedAt = now();
      this.persistent = false;
      this.storageError = null;
      this.loadError = null;
      this.leafCache = new Map();
      this.roadmapLeafCache = new Map();
      this.stageCache = new Map();
      this.roadmapCache = new Map();
      this.groupCache = new Map();
      try {
        this.storage = window.localStorage;
        const probe = STORAGE_KEY + '-storage-check';
        const oldProbe = this.storage.getItem(probe);
        this.storage.setItem(probe, '1');
        if (oldProbe === null) this.storage.removeItem(probe); else this.storage.setItem(probe, oldProbe);
        this.persistent = true;
        const saved = this.storage.getItem(STORAGE_KEY);
        if (saved) {
          try {
            if (saved.length > MAX_BYTES) throw new Error('Saved progress exceeds the 2 MB size limit.');
            const parsed = this.validateImport(JSON.parse(saved));
            this.manual = parsed.stages;
            this.updatedAt = parsed.updatedAt;
          } catch (error) { this.loadError = error.message; }
        }
      } catch (error) { this.persistent = false; this.storageError = error.message; }
    }

    reportedRecord(kind, id) {
      const records = this.overlay[kind];
      return records && own(records, id) && records[id] && STATUSES.has(records[id].status) ? records[id] : null;
    }

    sourceRecord(id) {
      // Imported evidence is mapped explicitly to stage IDs; broad roadmap reports
      // remain separately visible and never silently fill unreported targets.
      return this.reportedRecord('stages', id);
    }

    descendants(id) {
      if (!this.stages.has(id)) throw new Error('Unknown layer: ' + id);
      const found = new Set();
      const visit = current => {
        if (found.has(current)) return;
        found.add(current);
        (this.children.get(current) || []).forEach(visit);
      };
      visit(id);
      return Array.from(found);
    }

    leaves(id) {
      if (this.leafCache.has(id)) return this.leafCache.get(id);
      const found = new Set();
      const visited = new Set();
      const visit = current => {
        if (visited.has(current)) return;
        visited.add(current);
        const children = this.children.get(current) || [];
        if (!children.length) found.add(current);
        else children.forEach(visit);
      };
      if (this.stages.has(id)) visit(id);
      const result = Array.from(found);
      this.leafCache.set(id, result);
      return result;
    }

    roadmapLeaves(id, seen) {
      if (this.roadmapLeafCache.has(id)) return this.roadmapLeafCache.get(id);
      if (!this.roadmaps.has(id)) return [];
      seen = seen || new Set();
      if (seen.has(id)) return [];
      seen.add(id);
      const targets = this.byOwner.get(id) || [];
      const result = new Set();
      if (targets.length) targets.forEach(stageId => this.leaves(stageId).forEach(leafId => result.add(leafId)));
      else (this.roadmapChildren.get(id) || []).forEach(child => this.roadmapLeaves(child, new Set(seen)).forEach(leafId => result.add(leafId)));
      const leaves = Array.from(result);
      this.roadmapLeafCache.set(id, leaves);
      return leaves;
    }

    leafState(id) {
      const manual = this.manual.get(id);
      const record = this.sourceRecord(id);
      if (manual) return {
        status: manual.status, percent: percentFor(manual.status), basis: 'local_override',
        evidence: record && Array.isArray(record.evidence) ? record.evidence : [], note: manual.note,
        manual: true, updatedAt: manual.updatedAt, reportedStatus: record ? record.status : undefined,
        reportedBasis: record ? record.basis : undefined, snapshotStatus: 'manual'
      };
      if (record) return {
        status: record.status, percent: percentFor(record.status), basis: 'recorded_status',
        evidence: Array.isArray(record.evidence) ? record.evidence : [], note: '', manual: false,
        reportedStatus: record.status, reportedBasis: record.basis || '',
        snapshotStatus: record.snapshotStatus || 'reported', snapshotDate: record.snapshotDate,
        commit: record.commit, sourceRepositoryCommit: record.sourceRepositoryCommit
      };
      return { status: 'unknown', percent: 0, basis: 'unreported', evidence: [], note: '', manual: false, snapshotStatus: 'unknown' };
    }

    aggregate(ids) {
      const unique = Array.from(new Set(ids));
      const summary = { complete: 0, active: 0, unknown: 0, planned: 0, total: unique.length, percent: 0, manual: false, basis: 'unreported' };
      let reported = false;
      unique.forEach(id => {
        const state = this.leafState(id);
        if (state.status === 'complete') summary.complete++;
        else if (state.status === 'in_progress') summary.active++;
        else if (state.status === 'planned') summary.planned++;
        else summary.unknown++;
        summary.manual = summary.manual || state.manual;
        reported = reported || state.basis === 'recorded_status';
      });
      summary.percent = summary.total ? summary.complete / summary.total * 100 : 0;
      summary.basis = summary.manual ? 'local_override' : reported ? 'recorded_status' : 'unreported';
      return summary;
    }

    stage(id) {
      if (!this.stages.has(id)) throw new Error('Unknown layer: ' + id);
      if (this.stageCache.has(id)) return this.stageCache.get(id);
      const children = this.children.get(id) || [];
      if (!children.length) {
        const state = this.leafState(id);
        this.stageCache.set(id, state);
        return state;
      }
      const summary = this.aggregate(this.leaves(id));
      const record = this.sourceRecord(id);
      const ownManual = this.manual.get(id);
      const status = summary.total && summary.complete === summary.total ? 'complete'
        : summary.complete || summary.active ? 'in_progress'
        : summary.unknown || !summary.total ? 'unknown' : 'planned';
      const evidence = new Map();
      const includeEvidence = entry => {
        if (entry && Array.isArray(entry.evidence)) entry.evidence.forEach(item => {
          const key = [item.path || item.repositoryPath || '', item.lineStart || '', item.lineEnd || '', item.quote || ''].join('|');
          if (!evidence.has(key)) evidence.set(key, item);
        });
      };
      includeEvidence(record);
      this.leaves(id).forEach(leafId => includeEvidence(this.sourceRecord(leafId)));
      const state = Object.assign({}, summary, {
        status, percent: percentFor(status), completionPercent: summary.percent,
        basis: ownManual || summary.manual ? 'local_override' : summary.basis,
        evidence: Array.from(evidence.values()), note: ownManual ? ownManual.note : '',
        manual: !!ownManual || summary.manual,
        reportedStatus: record ? record.status : undefined, reportedBasis: record ? record.basis : undefined,
        snapshotStatus: ownManual || summary.manual ? 'manual' : record ? record.snapshotStatus || 'reported' : summary.basis === 'recorded_status' ? 'reported' : 'unknown',
        snapshotDate: record ? record.snapshotDate : undefined, aggregated: true
      });
      this.stageCache.set(id, state);
      return state;
    }

    roadmap(id) {
      if (!this.roadmaps.has(id)) throw new Error('Unknown roadmap: ' + id);
      if (this.roadmapCache.has(id)) return this.roadmapCache.get(id);
      const summary = this.aggregate(this.roadmapLeaves(id));
      const record = this.reportedRecord('roadmaps', id);
      if (record) Object.assign(summary, {
        reportedStatus: record.status, reportedBasis: record.basis || '',
        evidence: Array.isArray(record.evidence) ? record.evidence : [],
        snapshotStatus: record.snapshotStatus || 'reported', snapshotDate: record.snapshotDate,
        commit: record.commit, sourceRepositoryCommit: record.sourceRepositoryCommit
      });
      else Object.assign(summary, { evidence: [], snapshotStatus: summary.manual ? 'manual' : 'unknown' });
      summary.collection = !(this.byOwner.get(id) || []).length && !!(this.roadmapChildren.get(id) || []).length;
      this.roadmapCache.set(id, summary);
      return summary;
    }

    group(id) {
      if (!this.groups.has(id)) throw new Error('Unknown subject group: ' + id);
      if (this.groupCache.has(id)) return this.groupCache.get(id);
      const group = this.groups.get(id);
      const roadmapIds = new Set(Array.isArray(group.roadmapIds) ? group.roadmapIds : []);
      this.roadmaps.forEach(roadmap => { if (roadmap.group === id) roadmapIds.add(roadmap.id); });
      const leafIds = new Set();
      roadmapIds.forEach(roadmapId => this.roadmapLeaves(roadmapId).forEach(stageId => leafIds.add(stageId)));
      const summary = this.aggregate(Array.from(leafIds));
      this.groupCache.set(id, summary);
      return summary;
    }

    setStage(id, status, note) {
      if (!STATUSES.has(status)) throw new Error('Status must be planned, in_progress, complete, or unknown.');
      if (note === undefined) note = '';
      if (typeof note !== 'string' || note.length > MAX_NOTE) throw new Error('Notes must be text of at most ' + MAX_NOTE + ' characters.');
      const ids = this.descendants(id);
      const updatedAt = now();
      ids.forEach(stageId => this.manual.set(stageId, { status, note, updatedAt }));
      this.changed(updatedAt);
      return ids.length;
    }

    resetStage(id) {
      const ids = this.descendants(id);
      let count = 0;
      ids.forEach(stageId => { if (this.manual.delete(stageId)) count++; });
      if (count) this.changed(now());
      return count;
    }

    export() {
      const stages = Object.create(null);
      this.manual.forEach((record, id) => { stages[id] = { status: record.status, note: record.note, updatedAt: record.updatedAt }; });
      return { version: 1, updatedAt: this.updatedAt, stages };
    }

    validateImport(object) {
      if (!plainObject(object)) throw new Error('Progress must be a JSON object.');
      if (object.version !== 1) throw new Error('Unsupported progress version; expected version 1.');
      if (!plainObject(object.stages)) throw new Error('Progress must contain a stages object.');
      let serialized;
      try { serialized = JSON.stringify(object); } catch (_) { throw new Error('Progress must contain only serializable JSON data.'); }
      if (serialized.length > MAX_BYTES) throw new Error('Progress exceeds the 2 MB size limit.');
      if (object.updatedAt !== undefined && !validDate(object.updatedAt)) throw new Error('Progress updatedAt must be a valid date.');
      const entries = Object.entries(object.stages);
      if (entries.length > this.stages.size) throw new Error('Progress contains too many layers.');
      const updatedAt = object.updatedAt || now();
      const clean = new Map();
      entries.forEach(([id, record]) => {
        if (!this.stages.has(id)) throw new Error('Progress names an unknown layer: ' + id);
        if (!plainObject(record)) throw new Error('Invalid progress record for ' + id);
        if (!STATUSES.has(record.status)) throw new Error('Invalid status for ' + id);
        if (record.note !== undefined && (typeof record.note !== 'string' || record.note.length > MAX_NOTE)) throw new Error('Invalid note for ' + id);
        if (record.updatedAt !== undefined && !validDate(record.updatedAt)) throw new Error('Invalid updatedAt for ' + id);
        clean.set(id, { status: record.status, note: record.note || '', updatedAt: record.updatedAt || updatedAt });
      });
      return { stages: clean, updatedAt };
    }

    import(object) {
      const parsed = this.validateImport(object);
      this.manual = parsed.stages;
      this.changed(parsed.updatedAt);
      return this.manual.size;
    }

    changed(updatedAt) {
      this.updatedAt = updatedAt;
      this.stageCache.clear(); this.roadmapCache.clear(); this.groupCache.clear();
      if (this.persistent && this.storage) {
        try { this.storage.setItem(STORAGE_KEY, JSON.stringify(this.export())); }
        catch (error) { this.persistent = false; this.storageError = error.message; }
      }
      this.listeners.forEach(listener => { try { listener(this); } catch (error) { if (window.console) window.console.error('Progress listener failed:', error); } });
    }

    subscribe(listener) {
      if (typeof listener !== 'function') throw new Error('Progress subscriber must be a function.');
      this.listeners.add(listener);
      return () => this.listeners.delete(listener);
    }
  }

  TauProgress.STORAGE_KEY = STORAGE_KEY;
  window.TauProgress = TauProgress;
})();
