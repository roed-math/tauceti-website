"""Red-team jobs in the queue (research/blueprint/make_queue.py, PROTOCOL.md section 17)."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "blueprint"))
import make_queue  # noqa: E402


class AreaParts(unittest.TestCase):
    def test_a_small_area_is_one_part(self):
        members = [f"R{i}" for i in range(8)]
        self.assertEqual(make_queue.area_parts(members, []), [members])

    def test_a_large_area_splits_into_parts_that_keep_linked_roadmaps_together(self):
        first, second = [f"A{i}" for i in range(8)], [f"B{i}" for i in range(7)]
        links = [(a, b) for a in first for b in first if a < b] + [(a, b) for a in second for b in second if a < b] + [("A0", "B0")]
        self.assertEqual(make_queue.area_parts(sorted(first + second), links), [first, second])

    def test_parts_are_balanced_and_cover_the_area_once(self):
        members = [f"R{i:02d}" for i in range(23)]
        parts = make_queue.area_parts(members, [])
        self.assertEqual(sorted(map(len, parts)), [7, 8, 8])
        self.assertEqual(sorted(r for part in parts for r in part), members)


class Prompts(unittest.TestCase):
    def test_jobs_that_check_or_extract_are_not_told_to_continue_a_decomposition(self):
        for template in (make_queue.PAPER_TEMPLATE, make_queue.REDTEAM_TEMPLATE, make_queue.REDTEAM_AREA_TEMPLATE, make_queue.FIX_TEMPLATE):
            self.assertNotIn("Build on it: keep its node ids", template)
            self.assertIn("- Library baseline (what exists today):", template)


class Verdicts(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.folder = tempfile.TemporaryDirectory()
        self.saved = make_queue.REPO, make_queue.BP
        make_queue.REPO = Path(self.folder.name)
        make_queue.BP = make_queue.REPO / "research" / "blueprint"
        for name in ("restructure", "papers"):
            (make_queue.BP / name).mkdir(parents=True)

    def tearDown(self):
        make_queue.REPO, make_queue.BP = self.saved
        self.folder.cleanup()

    def test_only_work_its_review_accepted_counts_as_accepted(self):
        job = {"id": "RS-01", "kind": "restructure", "outputs": ["research/blueprint/restructure/RS-01.result.json", "research/blueprint/restructure/RS-01.md"]}
        result = make_queue.BP / "restructure" / "RS-01.result.json"
        result.write_text(json.dumps({"family": "RS-01", "review": {"status": "needs_changes"}}))
        self.assertFalse(make_queue.accepted_work(job))
        self.assertEqual(make_queue.review_status(job["outputs"][0]), "needs_changes")
        result.write_text(json.dumps({"family": "RS-01", "review": {"status": "accepted"}}))
        self.assertTrue(make_queue.accepted_work(job))

    def test_a_paper_is_accepted_by_its_review_file(self):
        job = {"id": "PAPER-X", "kind": "paper", "outputs": ["research/blueprint/papers/PAPER-X.result.json"]}
        self.assertFalse(make_queue.accepted_work(job))
        (make_queue.BP / "papers" / "PAPER-X.review.json").write_text(json.dumps({"paper": "PAPER-X", "verdict": "accept"}))
        self.assertTrue(make_queue.accepted_work(job))


class FixRouting(unittest.TestCase):
    """A fix to a roadmap's plan goes to its blueprint (PROTOCOL.md section 17)."""
    KNOWN = {"KTheoryLowDegrees", "PeriodsAndSpecialValues", "MotivesAndAlgebraicCycles"}

    def test_a_finding_names_its_roadmap_by_a_layer_or_by_the_roadmap_s_files(self):
        self.assertEqual(make_queue.finding_layers({"where": "KTheoryLowDegrees:U.4"}, self.KNOWN),
                         ({"KTheoryLowDegrees"}, {"KTheoryLowDegrees:U.4"}))
        roadmaps, _ = make_queue.finding_layers({"where": "content/campaign/PeriodsAndSpecialValues/README.md, PS.2 (see MotivesAndAlgebraicCycles)"}, self.KNOWN)
        self.assertEqual(roadmaps, {"PeriodsAndSpecialValues"})
        self.assertEqual(make_queue.finding_layers({"where": "tauceti:TauCetiRoadmap/LocalFieldsRamification"}, self.KNOWN), (set(), set()))

    def test_a_finding_goes_to_the_part_that_owns_its_layer(self):
        parts = [{"id": "BP-R--A.1", "scope": ["R:A.1", "R:A.2"]}, {"id": "BP-R--B.1", "scope": ["R:B.1"]}]
        self.assertEqual([j["id"] for j in make_queue.owning_parts("R", {"R:B.1"}, parts)], ["BP-R--B.1"])
        self.assertEqual([j["id"] for j in make_queue.owning_parts("R", set(), parts)], ["BP-R--A.1", "BP-R--B.1"])

    def test_the_findings_a_blueprint_is_handed_fit_its_prompt(self):
        items = [("RT-AREA-x", {"id": f"RT-AREA-x/{n}", "severity": "medium", "kind": "missing", "where": f"R:A.{n}",
                                "claim": "c" * 900, "fix": "f" * 400}) for n in range(40)]
        text = make_queue.handed_text(items)
        self.assertLess(len(text), make_queue.HANDED_BUDGET)
        self.assertIn("RT-AREA-x/39", text)
        self.assertIn("research/blueprint/redteam/RT-AREA-x.result.json", text)
        self.assertIn("c" * 900, make_queue.handed_text(items[:2]))

    def test_a_fix_that_goes_live_is_reviewed_first(self):
        jobs = {j["id"]: j for j in json.loads((ROOT / "research" / "blueprint" / "queue.json").read_text())["jobs"]}
        checked = 0
        for jid, job in jobs.items():
            live = [o for o in job["outputs"] if make_queue.PROMOTABLE.match(o)] if job["kind"] == "fix" else []
            if not live:
                continue
            review = jobs.get("REV-" + jid)
            self.assertIsNotNone(review, jid)
            self.assertEqual(review["after"], [jid])
            self.assertIn(jid, review["independentOf"])
            self.assertTrue(set(live) <= set(review["outputs"]), jid)
            checked += 1
        self.assertTrue(checked)

    def test_a_later_round_of_a_fix_follows_a_finished_one(self):
        jobs = {j["id"]: j for j in json.loads((ROOT / "research" / "blueprint" / "queue.json").read_text())["jobs"]}
        for jid, job in jobs.items():
            if job["kind"] != "fix" or "~" not in jid:
                continue
            base, _, number = jid.partition("~")
            earlier = base if number == "2" else f"{base}~{int(number) - 1}"
            self.assertEqual(jobs[earlier].get("state"), "done", jid)
            self.assertIn(job["after"], ([earlier], ["REV-" + earlier]), jid)
            self.assertIn(f"{base[4:]}.fixes-{number}.md", job["outputs"][0], jid)


class Restructuring(unittest.TestCase):
    def test_a_family_blueprint_follows_its_accepted_restructuring(self):
        note = make_queue.restructuring_note("RS-07")
        for rule in ("research/blueprint/restructure/RS-07.result.json", "keeps", "drops", "closed", "title and base"):
            self.assertIn(rule, note)


class Queue(unittest.TestCase):
    def test_a_proposal_its_review_sent_back_is_revised_before_its_family_is_blueprinted(self):
        jobs = {j["id"]: j for j in json.loads((ROOT / "research" / "blueprint" / "queue.json").read_text())["jobs"]}
        families = sorted(jid for jid, j in jobs.items() if j["kind"] == "restructure" and "~" not in jid)
        checked = 0
        for rs in families:
            path = ROOT / "research" / "blueprint" / "restructure" / f"{rs}.result.json"
            if make_queue.review_status(str(path.relative_to(ROOT))) != "needs_changes" or jobs.get("REV-" + rs, {}).get("state") != "done":
                continue
            # Each round waits for the review of the one before; a round's own deliverable is its
            # handoff note, since the proposal is revised in place.
            rounds = sorted(int(jid.partition("~")[2]) for jid in jobs if jid.startswith(rs + "~"))
            self.assertTrue(rounds, rs)
            previous = rs
            for n in rounds:
                revision = f"{rs}~{n}"
                self.assertEqual(jobs[revision]["after"], ["REV-" + previous])
                self.assertEqual(jobs["REV-" + revision]["after"], [revision])
                self.assertIn(f"research/blueprint/handoff/{revision}.md", jobs[revision]["outputs"])
                previous = revision
            members = jobs[rs]["roadmapIds"]
            waiting = [j for j in jobs.values() if j["kind"] == "blueprint" and j["roadmapIds"][0] in members and j.get("state") == "pending"]
            self.assertTrue(all("REV-" + previous in j["after"] for j in waiting), rs)
            self.assertNotIn("RT-" + rs, jobs)
            checked += 1
        self.assertTrue(checked)

    def test_a_fix_prompt_fits_in_an_issue_however_many_findings_it_has(self):
        findings = [{"id": f"F{n}", "severity": "major", "kind": "missing", "where": f"research/blueprint/audit/AUDIT-01.result.json, target T{n}",
                     "claim": "x" * 1500, "fix": "y" * 500} for n in range(98)]
        text = make_queue.findings_text("RT-AREA-topology", findings)
        self.assertLess(len(text), make_queue.FINDINGS_BUDGET)
        self.assertIn("F97", text)
        self.assertIn("research/blueprint/redteam/RT-AREA-topology.result.json", text)
        few = findings[:2]
        self.assertIn("x" * 1500, make_queue.findings_text("RT-X", few))

    def test_a_fix_job_is_given_the_paths_its_findings_name_not_their_descriptions(self):
        editable, elsewhere = make_queue.finding_files([
            {"where": "research/blueprint/papers/PAPER-X.result.json, item PAPER-X/cm-newform (planned)"},
            {"where": "items in research/blueprint/audit/AUDIT-01.result.json and research/blueprint/atlas/roadmaps/R.json"},
            {"where": "the report"}])
        self.assertEqual(editable, ["research/blueprint/audit/AUDIT-01.result.json", "research/blueprint/papers/PAPER-X.result.json"])
        self.assertEqual(elsewhere, ["research/blueprint/atlas/roadmaps/R.json"])

    def test_a_verifier_is_independent_of_the_red_team_and_of_the_work_it_attacked(self):
        jobs = {j["id"]: j for j in json.loads((ROOT / "research" / "blueprint" / "queue.json").read_text())["jobs"]}
        verifications = [j for jid, j in jobs.items() if jid.startswith("REV-RT-")]
        self.assertTrue(verifications)
        for verification in verifications:
            red = jobs[verification["id"][4:]]
            self.assertEqual(set(verification.get("independentOf") or []), {red["id"], *red["independentOf"]}, verification["id"])


class Reviews(unittest.TestCase):
    def test_a_review_may_write_its_verdict_into_the_files_it_reviews(self):
        # The verdict goes into the reviewed file (PROTOCOL.md section 8), and the
        # intake merges only a job's own outputs.
        jobs = {j["id"]: j for j in json.loads((ROOT / "research" / "blueprint" / "queue.json").read_text())["jobs"]}
        checked = 0
        for job in jobs.values():
            live = job["kind"] == "review" and job.get("state") != "superseded"
            target = jobs.get((job.get("after") or [None])[0]) if live else None
            if target and target["kind"] in ("blueprint", "design", "link", "restructure"):
                reviewed = {path for path in target["outputs"] if path.endswith(".json")}
                self.assertLessEqual(reviewed, set(job["outputs"]), job["id"])
                checked += 1
            if target and target["kind"] == "paper":
                # A paper's reviewer corrects the extraction and its report in place (PROTOCOL.md section 16).
                self.assertLessEqual(set(target["outputs"]), set(job["outputs"]), job["id"])
        self.assertGreater(checked, 300)


if __name__ == "__main__":
    unittest.main()
