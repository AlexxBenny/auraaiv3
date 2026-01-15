# Self-Evolution Implementation Order

## Recommended Implementation Sequence

Follow this exact order to build self-evolution safely.

---

## Step 1: Update Planner (Phase 3.1)

**File:** `agents/planner_agent.py`

**Changes:**
1. Add `requires_new_skill`, `missing_capability`, `reason` to `PLAN_SCHEMA`
2. Update `plan()` method to detect limitations
3. Add validation to ensure `requires_new_skill=true` → empty steps

**Test:** Run planner with command that needs missing tool

---

## Step 2: Create Limitation Analysis Agent (Phase 3.2)

**File:** `agents/limitation_agent.py` (NEW)

**Implementation:**
1. Copy template from `SELF_EVOLUTION_PLAN.md`
2. Implement `PROPOSAL_SCHEMA`
3. Implement `analyze()` method
4. Test with sample limitation

**Test:** Call `analyze()` with missing capability

---

## Step 3: Create Skill Gate (Phase 3.3)

**File:** `core/skill_gate.py` (NEW)

**Implementation:**
1. Copy template from plan
2. Implement validation logic
3. Set default mode to "manual"
4. Test validation with sample proposals

**Test:** Validate good and bad proposals

---

## Step 4: Create Procedural Memory (Phase 3.4)

**File:** `memory/procedural.py` (NEW)

**Implementation:**
1. Copy template from plan
2. Implement storage/retrieval
3. Test storing and retrieving proposals

**Test:** Store proposal, retrieve it, approve it

---

## Step 5: Create Tool Scaffold Generator (Phase 3.5)

**File:** `core/tool_scaffold.py` (NEW)

**Implementation:**
1. Copy template from plan
2. Implement template generation
3. Test generating scaffold file

**Test:** Generate scaffold, verify file created

---

## Step 6: Integrate into Agent Loop (Phase 3.6)

**File:** `core/agent_loop.py`

**Changes:**
1. Import new components
2. Initialize in `__init__()`
3. Add `_handle_missing_skill()` method
4. Update `process()` to call limitation handler

**Test:** End-to-end flow with missing skill

---

## Step 7: Enhance Critic (Phase 3.7)

**File:** `agents/critic_agent.py`

**Changes:**
1. Add tool effectiveness evaluation
2. Connect to procedural memory
3. Add feedback loop

**Test:** Evaluate tool performance

---

## Step 8: Add Configuration (Phase 4)

**File:** `config/settings.yaml` (NEW)

**Implementation:**
1. Create settings file
2. Add evolution configuration
3. Update components to read config

**Test:** Change autonomy mode, verify behavior

---

## Step 9: Add Logging

**Enhancements:**
1. Log all proposals
2. Log validations
3. Log registrations
4. Add audit trail

**Test:** Verify all actions logged

---

## Step 10: Documentation

**Files:**
1. Update `ARCHITECTURE.md`
2. Update `MIGRATION_STATUS.md`
3. Create user guide for tool proposals

---

## Quick Start (Minimal Viable)

To get basic self-evolution working:

1. ✅ Update Planner (Step 1)
2. ✅ Create Limitation Agent (Step 2)
3. ✅ Create Skill Gate (Step 3)
4. ✅ Create Procedural Memory (Step 4)
5. ✅ Integrate into Agent Loop (Step 6)

This gives you:
- Limitation detection
- Proposal generation
- Validation
- Storage

Scaffold generation and feedback loops can be added later.

---

## Testing After Each Step

After each step, run:

```bash
python test_architecture.py
```

Then test the specific feature:
- Step 1: Test planner with missing tool
- Step 2: Test limitation analysis
- Step 3: Test validation
- Step 4: Test storage
- Step 5: Test scaffold generation
- Step 6: Test end-to-end flow

---

*Follow this order for safe, incremental implementation.*

