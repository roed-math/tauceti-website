(function () {
  'use strict';

  // Presentation never changes source records, dependency IDs or progress totals.
  // Curated prose is kept separately; fallback passages are selected from the source.
  function create(data) {
    const stages = new Map(data.stages.map(stage => [stage.id, stage]));
    const overrides = data.stagePresentation || {};
    const children = new Map(), summaries = new Map();
    for (const stage of data.stages) {
      if (!stage.parentStageId) continue;
      if (!children.has(stage.parentStageId)) children.set(stage.parentStageId, []);
      children.get(stage.parentStageId).push(stage);
    }
    function stageTitle(id) {
      const stage = stages.get(id);
      return overrides[id]?.title || String(stage?.title || stage?.key || id)
        .replace(/^(?:layer|stage|lane|phase|step|milestone)\s+(?:(?:[A-Z]{1,3}(?:[ .-]?\d+)*|\d+(?:\.\d+)*[a-z]?)\s*)?[:,—–-]\s*/i, '')
        .replace(/^\p{Ll}/u, letter => letter.toUpperCase());
    }
    function isMathematicalStage(id) { return !overrides[id]?.hidden; }
    function stageSummary(id) {
      if (summaries.has(id)) return summaries.get(id);
      const stage = stages.get(id);
      const result = overrides[id]?.summary || (stage ? mathematicalPassages(TauLandmarks.passages(stage, children.get(id))).slice(0, 2).join('\n\n') : '');
      summaries.set(id, result);
      return result;
    }
    return Object.freeze({ stageTitle, stageSummary, isMathematicalStage });
  }

  function mathematicalPassages(passages) {
    const metadata = /^(?:inputs?|dependenc(?:y|ies)|source(?: route|s| unit)?|execution state|implementation|acceptance|references?|prerequisites?|consumers?|status|original prerequisites|scope note)\b/i;
    const workflow = /\b(?:roadmaps?|audits?|readiness|checkpoints?|scratch checkout|source-to-Lean|Mathlib|sorry-free|proof tasks?|source[- ](?:route|decomposition|concordance)|owners?|ownership|suppliers?|reexports?|exports?|APIs?|interfaces?|registr(?:y|ies)|repository|source PR|named deliverable|pinned commit)\b/i;
    return passages.flatMap(passage => {
      let text = passage.trim();
      if (!text || /^#{1,6}\s|^<a\b|```|^\|/.test(text)) return [];
      const label = /^(?:[-*+]\s+|\d+[.)]\s+)?\*\*([^*]+)\*\*\s*[:.]?\s*/.exec(text);
      if (label && metadata.test(label[1])) return [];
      text = text.replace(/^(?:[-*+]\s+|\d+[.)]\s+)?\*\*(?:construct(?:ion)?(?: and export)?|target|goal|output)\s*[.:]?\*\*\s*[:.]?\s*/i, '');
      text = text.split(/(?<=[.!?])\s+(?=[A-Z])/).filter(sentence => !workflow.test(sentence)).join(' ');
      if (text.length < 35) return [];
      return [text];
    });
  }

  // Planet excerpts retain hypotheses and equations while removing a workflow heading.
  function landmarkDescription(item) {
    return item.description.replace(/^(?:[-*+]\s+|\d+[.)]\s+)?\*\*(?:construct(?:ion)?(?: and export)?|acceptance(?: examples)?|target|goal|output)\s*[.:]?\*\*\s*[:.]?\s*/i, '')
      .replace(/\bMatch the existing Dirichlet-series carrier and normalization\.\s*/g, '');
  }
  window.TauPresentation = Object.freeze({ create, landmarkDescription });
})();
