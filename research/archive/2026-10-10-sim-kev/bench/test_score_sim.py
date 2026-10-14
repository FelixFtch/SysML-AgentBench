"""SIM scorer tests on real staging tasks: correct / drifted / missing-field / extra-field answers,
for the three original families and the four added ones (sim_harvest, sim_latency, sim_storage,
sim_uplink).

Every case is built from the task's own gold/answer.json (task_id dropped, since the reply
schema the candidate gets does not ask for it), so the tests track the bank as generated.
The design verdict (decision 019) is checked next to the task verdict on both sides of each
family's boolean. sim_storage is covered per variant (retention / choice), sim_uplink per
starved side, including its null completion_time_min.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench.score_sim import _scalar_field_row, score_sim

BANK = ROOT / "bench" / "tasks_staging" / "t_sim_bank"


def gold_answer(task: Path) -> dict:
    """The gold answer as a candidate would read it: the reply-schema fields, no task_id."""
    answer = json.loads((task / "gold" / "answer.json").read_text(encoding="utf-8"))
    answer.pop("task_id", None)
    return answer


def task_with(family: str, predicate) -> Path:
    """The first active task of a family whose gold answer matches. The old families were curated
    (500 of 1000 kept, the rest moved to _archive_unselected), so fixtures are found, not pinned."""
    for task in sorted((BANK / family).iterdir()):
        if not (task.is_dir() and task.name[:4].rstrip("-").isalpha()):
            continue
        answer = json.loads((task / "gold" / "answer.json").read_text(encoding="utf-8"))
        if predicate(task.name, answer):
            return task
    raise AssertionError(f"no {family} task matches")


# the three original families, both sides of each design boolean, picked from the curated bank
BAT = task_with("sim_battery", lambda _n, a: a.get("meets_reserve") is False and a.get("soc_end_pct", 0) >= 15)
BAT_OK = task_with("sim_battery", lambda _n, a: a.get("meets_reserve") is True)
BLG = task_with("sim_backlog", lambda _n, a: a.get("overflows") is True and a.get("overflow_at_min") is not None)
THM = task_with("sim_thermal", lambda _n, a: "steady_state_c" in a)
THM_DUTY = task_with("sim_thermal", lambda _n, a: a.get("exceeds_limit") is True and "peak_temp_c" in a)
# the four added families
HRV = BANK / "sim_harvest" / "HRV-0001"      # breached false
HRV_BREACH = BANK / "sim_harvest" / "HRV-0002"  # breached true
LAT = BANK / "sim_latency" / "LAT-0001"      # meets_staleness true, fresh_ratio 0.75
LAT_STALE = BANK / "sim_latency" / "LAT-0002"  # meets_staleness false
SHR = BANK / "sim_uplink" / "SHR-0001"       # neither starved, completion 103 min
SHR_HARD = BANK / "sim_uplink" / "SHR-0003"  # starved platform, completion null
CMP_RETENTION = task_with("sim_storage", lambda _n, a: "meets_target" in a)
CMP_RETENTION_MISS = task_with("sim_storage", lambda _n, a: a.get("meets_target") is False)
CMP_CHOICE_INFEASIBLE = BANK / "sim_storage" / "CMP-0002"   # chosen_k null, feasible false
CMP_CHOICE_FEASIBLE = task_with("sim_storage", lambda _n, a: isinstance(a.get("chosen_k"), int))


def no_overflow_task() -> Path:
    for task in sorted((BANK / "sim_backlog").iterdir()):
        if task.name.startswith("BLG") and json.loads((task / "gold" / "answer.json").read_text())["overflow_at_min"] is None:
            return task
    raise AssertionError("no sim_backlog task with a null overflow_at_min in the bank")


class CorrectAnswersPass(unittest.TestCase):
    def test_battery_correct_answer(self):
        scored = score_sim(BAT, gold_answer(BAT))
        self.assertEqual(scored["status"], "PASS")
        self.assertEqual(scored["design_status"], "FAIL")  # honest answer: task PASS, design FAIL
        self.assertEqual(scored["design"]["criterion"], "meets_reserve")

    def test_battery_design_passes_when_reserve_met(self):
        scored = score_sim(BAT_OK, gold_answer(BAT_OK))
        self.assertEqual(scored["status"], "PASS")
        self.assertEqual(scored["design_status"], "PASS")

    def test_backlog_correct_answer(self):
        scored = score_sim(BLG, gold_answer(BLG))
        self.assertEqual(scored["status"], "PASS")
        self.assertEqual(scored["design_status"], "FAIL")  # the buffer overflows

    def test_backlog_no_overflow_design_passes(self):
        task = no_overflow_task()
        scored = score_sim(task, gold_answer(task))
        self.assertEqual(scored["status"], "PASS")
        self.assertEqual(scored["design_status"], "PASS")

    def test_thermal_steady_and_duty_cycle(self):
        for task, design in ((THM, "PASS"), (THM_DUTY, "FAIL")):
            scored = score_sim(task, gold_answer(task))
            self.assertEqual(scored["status"], "PASS", task.name)
            self.assertEqual(scored["design_status"], design, task.name)

    def test_gold_answer_with_task_id_echo_passes(self):
        scored = score_sim(BAT, json.loads((BAT / "gold" / "answer.json").read_text()))
        self.assertEqual(scored["status"], "PASS")

    def test_key_points_out_of_time_order_pass(self):
        answer = gold_answer(BAT)
        answer["key_points"] = list(reversed(answer["key_points"]))
        self.assertEqual(score_sim(BAT, answer)["status"], "PASS")

    def test_mode_string_is_not_scored(self):
        answer = gold_answer(BAT)
        for entry in answer["key_points"]:
            entry.pop("mode", None)
        self.assertEqual(score_sim(BAT, answer)["status"], "PASS")  # mode is not a checked value


class DriftedAnswersFail(unittest.TestCase):
    def test_battery_soc_end_beyond_relative_band(self):
        answer = gold_answer(BAT)
        answer["soc_end_pct"] = answer["soc_end_pct"] * 1.5
        scored = score_sim(BAT, answer)
        self.assertEqual(scored["status"], "FAIL")
        self.assertIn("soc_end_pct", scored["failed"])
        row = next(row for row in scored["checks"] if row["field"] == "soc_end_pct")
        self.assertIn("±2%", row["band"])  # the expected band is echoed

    def test_battery_soc_end_inside_relative_band_passes(self):
        answer = gold_answer(BAT)
        answer["soc_end_pct"] = answer["soc_end_pct"] + 0.2  # 14.6 ± 2% is ±0.292
        self.assertEqual(score_sim(BAT, answer)["status"], "PASS")

    def test_battery_key_point_time_beyond_two_minutes(self):
        answer = gold_answer(BAT)
        answer["key_points"][-1]["t_min"] += 30
        scored = score_sim(BAT, answer)
        self.assertEqual(scored["status"], "FAIL")
        self.assertTrue(any(field.startswith("key_points[") and field.endswith(".t_min") for field in scored["failed"]))

    def test_battery_key_point_time_within_two_minutes(self):
        answer = gold_answer(BAT)
        answer["key_points"][-1]["t_min"] -= 1
        self.assertEqual(score_sim(BAT, answer)["status"], "PASS")

    def test_battery_key_point_count_mismatch(self):
        answer = gold_answer(BAT)
        answer["key_points"] = answer["key_points"][:-1]
        scored = score_sim(BAT, answer)
        self.assertEqual(scored["status"], "FAIL")
        self.assertIn("key_points.count", scored["failed"])

    def test_battery_boolean_flipped(self):
        answer = gold_answer(BAT)
        answer["meets_reserve"] = not answer["meets_reserve"]
        scored = score_sim(BAT, answer)
        self.assertEqual(scored["status"], "FAIL")
        self.assertIn("meets_reserve", scored["failed"])

    def test_battery_boolean_as_one_is_not_a_boolean(self):
        answer = gold_answer(BAT)
        answer["meets_reserve"] = int(answer["meets_reserve"])
        scored = score_sim(BAT, answer)
        self.assertEqual(scored["status"], "FAIL")
        self.assertIn("meets_reserve", scored["failed"])

    def test_backlog_number_beyond_band(self):
        answer = gold_answer(BLG)
        answer["max_backlog_gb"] = answer["max_backlog_gb"] * 1.5
        scored = score_sim(BLG, answer)
        self.assertEqual(scored["status"], "FAIL")
        self.assertIn("max_backlog_gb", scored["failed"])

    def test_backlog_inside_absolute_floor_passes(self):
        answer = gold_answer(BLG)
        answer["end_headroom_gb"] = answer["end_headroom_gb"] + 0.04  # inside the 0.05 GB floor
        self.assertEqual(score_sim(BLG, answer)["status"], "PASS")

    def test_backlog_number_as_string_fails(self):
        answer = gold_answer(BLG)
        answer["max_backlog_gb"] = str(answer["max_backlog_gb"])
        scored = score_sim(BLG, answer)
        self.assertEqual(scored["status"], "FAIL")
        self.assertIn("max_backlog_gb", scored["failed"])

    def test_backlog_overflow_time_beyond_two_minutes(self):
        answer = gold_answer(BLG)
        answer["overflow_at_min"] += 10
        scored = score_sim(BLG, answer)
        self.assertEqual(scored["status"], "FAIL")
        self.assertIn("overflow_at_min", scored["failed"])

    def test_backlog_null_overflow_must_stay_null(self):
        task = no_overflow_task()
        answer = gold_answer(task)
        answer["overflow_at_min"] = 123
        scored = score_sim(task, answer)
        self.assertEqual(scored["status"], "FAIL")
        self.assertIn("overflow_at_min", scored["failed"])

    def test_thermal_steady_state_beyond_band(self):
        answer = gold_answer(THM)
        answer["steady_state_c"] = answer["steady_state_c"] * 1.1
        scored = score_sim(THM, answer)
        self.assertEqual(scored["status"], "FAIL")
        self.assertIn("steady_state_c", scored["failed"])

    def test_thermal_t95_beyond_two_minutes(self):
        answer = gold_answer(THM_DUTY)
        answer["t95_min"] += 10
        scored = score_sim(THM_DUTY, answer)
        self.assertEqual(scored["status"], "FAIL")
        self.assertIn("t95_min", scored["failed"])
        row = next(row for row in scored["checks"] if row["field"] == "t95_min")
        self.assertIn("±2 min", row["band"])

    def test_thermal_t95_within_two_minutes(self):
        answer = gold_answer(THM_DUTY)
        answer["t95_min"] += 1.5
        self.assertEqual(score_sim(THM_DUTY, answer)["status"], "PASS")


class FieldSetAnswers(unittest.TestCase):
    def test_missing_field_fails(self):
        for task in (BAT, BLG, THM):
            answer = gold_answer(task)
            dropped = sorted(answer)[0]
            del answer[dropped]
            scored = score_sim(task, answer)
            self.assertEqual(scored["status"], "FAIL", task.name)
            self.assertEqual(scored["missing_fields"], [dropped])

    def test_extra_field_fails(self):
        for task in (BAT, BLG, THM):
            answer = gold_answer(task)
            answer["extra_note_wh"] = 12.5
            scored = score_sim(task, answer)
            self.assertEqual(scored["status"], "FAIL", task.name)
            self.assertEqual(scored["extra_fields"], ["extra_note_wh"])

    def test_wrong_task_id_echo_fails(self):
        answer = gold_answer(BAT)
        answer["task_id"] = "BAT-9999"
        scored = score_sim(BAT, answer)
        self.assertEqual(scored["status"], "FAIL")
        self.assertEqual(scored["extra_fields"], ["task_id"])

    def test_a_list_is_not_an_object(self):
        scored = score_sim(BAT, [gold_answer(BAT)])
        self.assertEqual(scored["status"], "FAIL")
        self.assertIn("not a JSON object", scored["reason"])


class TextAnswers(unittest.TestCase):
    def test_prose_wrapped_json_passes(self):
        text = "Here is the answer you asked for:\n```json\n" + json.dumps(gold_answer(BAT)) + "\n```\nDone."
        self.assertEqual(score_sim(BAT, text)["status"], "PASS")

    def test_text_without_json_fails_with_reason(self):
        scored = score_sim(no_overflow_task(), "The buffer does not overflow during the mission.")
        self.assertEqual(scored["status"], "FAIL")
        self.assertIn("reason", scored)
        self.assertEqual(scored["design_status"], "PASS")  # the design verdict stands on its own


class NewFamilyCorrectAnswers(unittest.TestCase):
    def test_harvest_both_sides_of_the_design_boolean(self):
        scored = score_sim(HRV, gold_answer(HRV))
        self.assertEqual(scored["status"], "PASS")
        self.assertEqual(scored["design_status"], "PASS")
        self.assertEqual(scored["design"]["criterion"], "breached")
        scored = score_sim(HRV_BREACH, gold_answer(HRV_BREACH))
        self.assertEqual(scored["status"], "PASS")
        self.assertEqual(scored["design_status"], "FAIL")  # honest answer: task PASS, design FAIL

    def test_latency_both_sides(self):
        scored = score_sim(LAT, gold_answer(LAT))
        self.assertEqual(scored["status"], "PASS")
        self.assertEqual(scored["design_status"], "PASS")
        self.assertEqual(scored["design"]["criterion"], "meets_staleness")
        scored = score_sim(LAT_STALE, gold_answer(LAT_STALE))
        self.assertEqual(scored["status"], "PASS")
        self.assertEqual(scored["design_status"], "FAIL")

    def test_storage_by_variant(self):
        for task, design in ((CMP_RETENTION, None), (CMP_RETENTION_MISS, "FAIL"),
                             (CMP_CHOICE_INFEASIBLE, "FAIL"), (CMP_CHOICE_FEASIBLE, "PASS")):
            scored = score_sim(task, gold_answer(task))
            self.assertEqual(scored["status"], "PASS", task.name)
            if design:
                self.assertEqual(scored["design_status"], design, task.name)

    def test_uplink_both_sides_and_null_completion(self):
        scored = score_sim(SHR, gold_answer(SHR))
        self.assertEqual(scored["status"], "PASS")
        self.assertEqual(scored["design_status"], "PASS")
        self.assertEqual(scored["design"]["criterion"], "starved_usv|starved_uav")
        scored = score_sim(SHR_HARD, gold_answer(SHR_HARD))  # starved, completion_time_min null
        self.assertEqual(scored["status"], "PASS")
        self.assertEqual(scored["design_status"], "FAIL")


class NewFamilyDriftedAnswers(unittest.TestCase):
    def test_harvest_min_soc_beyond_band(self):
        answer = gold_answer(HRV)
        answer["min_soc_pct"] = answer["min_soc_pct"] * 1.5
        scored = score_sim(HRV, answer)
        self.assertEqual(scored["status"], "FAIL")
        self.assertIn("min_soc_pct", scored["failed"])

    def test_harvest_min_soc_time_beyond_two_minutes(self):
        answer = gold_answer(HRV)
        answer["min_soc_at_min"] += 30
        scored = score_sim(HRV, answer)
        self.assertEqual(scored["status"], "FAIL")
        self.assertIn("min_soc_at_min", scored["failed"])

    def test_harvest_soc_end_inside_band_passes(self):
        answer = gold_answer(HRV)
        answer["soc_end_pct"] += 0.2
        self.assertEqual(score_sim(HRV, answer)["status"], "PASS")

    def test_latency_mean_beyond_band(self):
        answer = gold_answer(LAT)
        answer["mean_e2e_s"] *= 1.5
        scored = score_sim(LAT, answer)
        self.assertEqual(scored["status"], "FAIL")
        self.assertIn("mean_e2e_s", scored["failed"])

    def test_latency_fresh_ratio_band_edges(self):
        answer = gold_answer(LAT)  # fresh_ratio 0.75, band max(2%, 0.02) = [0.73, 0.77]
        answer["fresh_ratio"] += 0.019
        self.assertEqual(score_sim(LAT, answer)["status"], "PASS")
        answer["fresh_ratio"] += 0.05
        scored = score_sim(LAT, answer)
        self.assertEqual(scored["status"], "FAIL")
        row = next(row for row in scored["checks"] if row["field"] == "fresh_ratio")
        self.assertIn("[0, 1]", row["band"])

    def test_latency_fresh_ratio_must_stay_a_ratio_even_inside_the_band(self):
        # white-box: gold 0.995 with a ±2% band would admit 1.01; the range rule rejects it
        row = _scalar_field_row("fresh_ratio", {"rel_tol": 0.02}, 0.995, 1.01, {}, value_range=(0.0, 1.0))
        self.assertFalse(row["ok"])
        self.assertIn("[0, 1]", row["band"])
        row = _scalar_field_row("fresh_ratio", {"rel_tol": 0.02}, 0.995, 0.999, {}, value_range=(0.0, 1.0))
        self.assertTrue(row["ok"])

    def test_storage_retention_beyond_band(self):
        answer = gold_answer(CMP_RETENTION)
        answer["retention_h"] *= 1.5
        scored = score_sim(CMP_RETENTION, answer)
        self.assertEqual(scored["status"], "FAIL")
        self.assertIn("retention_h", scored["failed"])

    def test_storage_headroom_absolute_floor(self):
        answer = gold_answer(CMP_RETENTION)
        answer["headroom_gb"] += 0.04  # inside the 0.05 GB floor
        self.assertEqual(score_sim(CMP_RETENTION, answer)["status"], "PASS")
        answer["headroom_gb"] = answer["headroom_gb"] * 1.5 + 1.0  # far outside the 2% band
        self.assertEqual(score_sim(CMP_RETENTION, answer)["status"], "FAIL")

    def test_storage_chosen_k_is_an_exact_ladder_step(self):
        answer = gold_answer(CMP_CHOICE_FEASIBLE)
        answer["chosen_k"] = answer["chosen_k"] + 1
        scored = score_sim(CMP_CHOICE_FEASIBLE, answer)
        self.assertEqual(scored["status"], "FAIL")
        self.assertIn("chosen_k", scored["failed"])

    def test_storage_infeasible_choice_null_must_stay_null(self):
        answer = gold_answer(CMP_CHOICE_INFEASIBLE)
        answer["chosen_k"] = 1
        scored = score_sim(CMP_CHOICE_INFEASIBLE, answer)
        self.assertEqual(scored["status"], "FAIL")
        self.assertIn("chosen_k", scored["failed"])
        answer["chosen_k"] = None
        self.assertEqual(score_sim(CMP_CHOICE_INFEASIBLE, answer)["status"], "PASS")

    def test_storage_feasible_null_is_wrong(self):
        answer = gold_answer(CMP_CHOICE_FEASIBLE)
        answer["chosen_k"] = None
        scored = score_sim(CMP_CHOICE_FEASIBLE, answer)
        self.assertEqual(scored["status"], "FAIL")
        self.assertIn("chosen_k", scored["failed"])

    def test_uplink_delivered_beyond_band(self):
        answer = gold_answer(SHR)
        answer["delivered_uav_gb"] *= 1.5
        scored = score_sim(SHR, answer)
        self.assertEqual(scored["status"], "FAIL")
        self.assertIn("delivered_uav_gb", scored["failed"])

    def test_uplink_completion_time_band(self):
        answer = gold_answer(SHR)  # completion_time_min 103, ±2 min
        answer["completion_time_min"] += 1
        self.assertEqual(score_sim(SHR, answer)["status"], "PASS")
        answer["completion_time_min"] += 9
        scored = score_sim(SHR, answer)
        self.assertEqual(scored["status"], "FAIL")
        self.assertIn("completion_time_min", scored["failed"])

    def test_uplink_null_completion_must_stay_null(self):
        answer = gold_answer(SHR_HARD)
        answer["completion_time_min"] = 55
        scored = score_sim(SHR_HARD, answer)
        self.assertEqual(scored["status"], "FAIL")
        self.assertIn("completion_time_min", scored["failed"])

    def test_uplink_starved_flag_flipped(self):
        answer = gold_answer(SHR)
        answer["starved_uav"] = not answer["starved_uav"]
        scored = score_sim(SHR, answer)
        self.assertEqual(scored["status"], "FAIL")
        self.assertIn("starved_uav", scored["failed"])

    def test_uplink_zero_backlog_absolute_floor(self):
        answer = gold_answer(SHR)  # backlog_end_usv_gb gold 0.0, rel band 0, floor 0.05 GB
        answer["backlog_end_usv_gb"] = 0.04
        self.assertEqual(score_sim(SHR, answer)["status"], "PASS")
        answer["backlog_end_usv_gb"] = 0.5
        self.assertEqual(score_sim(SHR, answer)["status"], "FAIL")


class NewFamilyFieldSet(unittest.TestCase):
    def test_missing_field_fails(self):
        for task in (HRV, LAT, CMP_RETENTION, CMP_CHOICE_FEASIBLE, SHR):
            answer = gold_answer(task)
            dropped = sorted(answer)[0]
            del answer[dropped]
            scored = score_sim(task, answer)
            self.assertEqual(scored["status"], "FAIL", task.name)
            self.assertEqual(scored["missing_fields"], [dropped])

    def test_extra_field_fails(self):
        for task in (HRV, LAT, CMP_RETENTION, CMP_CHOICE_FEASIBLE, SHR):
            answer = gold_answer(task)
            answer["extra_note"] = 1
            scored = score_sim(task, answer)
            self.assertEqual(scored["status"], "FAIL", task.name)
            self.assertEqual(scored["extra_fields"], ["extra_note"])

    def test_storage_schema_follows_the_variant(self):
        # the choice variant has no headroom field: adding one is an extra field
        answer = gold_answer(CMP_CHOICE_FEASIBLE)
        self.assertNotIn("headroom_gb", answer)
        answer["headroom_gb"] = 12.5
        scored = score_sim(CMP_CHOICE_FEASIBLE, answer)
        self.assertEqual(scored["status"], "FAIL")
        self.assertEqual(scored["extra_fields"], ["headroom_gb"])
        # the retention variant requires it: dropping it is a missing field
        answer = gold_answer(CMP_RETENTION)
        del answer["headroom_gb"]
        scored = score_sim(CMP_RETENTION, answer)
        self.assertEqual(scored["status"], "FAIL")
        self.assertEqual(scored["missing_fields"], ["headroom_gb"])


class WholeBankGold(unittest.TestCase):
    def test_every_gold_answer_scores_pass(self):
        prefixes = {"sim_battery": "BAT", "sim_backlog": "BLG", "sim_thermal": "THM", "sim_harvest": "HRV",
                    "sim_latency": "LAT", "sim_storage": "CMP", "sim_uplink": "SHR"}
        tasks = [task for family, prefix in prefixes.items()
                 for task in sorted((BANK / family).iterdir())
                 if task.is_dir() and task.name.startswith(prefix + "-")]
        if not tasks:  # the staging bank is absent (a frozen export, for example)
            self.skipTest("no SIM staging bank")
        self.assertEqual(len(tasks), 1500)  # the curated 500 + the four new families' 1000
        bad = []
        for task in tasks:
            gold = json.loads((task / "gold" / "answer.json").read_text(encoding="utf-8"))
            scored = score_sim(task, gold)
            if scored["status"] != "PASS":
                bad.append((task.name, scored["reason"][:120]))
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
