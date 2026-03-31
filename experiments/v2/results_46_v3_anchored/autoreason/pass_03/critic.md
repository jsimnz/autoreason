## Real Problems with This Proposal

### 1. The Version Fencing Logic Is Backwards

The Lua script deletes the cache entry if `data.version <= new_version`. This is the wrong condition. It will delete a *newer* cached value if a second write completes and caches version 5, and then a delayed invalidation from the first write runs with version 4. The correct condition is `data.version < new_version` (strictly less than), or more precisely, only delete if the cached version is the one being superseded. As written, the script can evict valid, up-to-date cache entries.

### 2. The Fast Path in APNsTokenManager Has a Data Race

The "fast path" reads `self._token` and `self._token_generated_at` outside the lock. In Python with CPython's GIL this is unlikely to cause corruption, but the comment claims this is acceptable because "worst case we enter the slow path." That's not the only worst case. A thread can read a non-None `self._token` on the fast path while another thread is mid-way through replacing it in the slow path, returning a partially-overwritten or just-expired token without entering the slow path at all. The double-checked locking pattern requires memory visibility guarantees that Python doesn't formally provide outside the lock.

### 3. The Peak Multiplier Is Applied Inconsistently

The document applies a 3× peak multiplier to derive ~1,530/sec from 44M/day, then sizes for 2,000/sec. But the aggressive scenario is 90M/day, which at 3× peak is ~3,125/sec — 56% above the stated sizing target of 2,000/sec. The document claims "infrastructure must handle the aggressive case without redesign" but then sizes infrastructure that demonstrably cannot handle it.

### 4. Worker Count Derivation Is Deferred but Never Present

Section 1.1 says "Worker counts are derived explicitly in Section 5." The document is cut off before Section 5 appears. This is not a document completeness issue — it's a substantive problem because worker counts are referenced as established facts (8 push workers, 4 in-app workers) before the derivation that would justify them. Reviewers are being asked to approve numbers without seeing the math.

### 5. The SMS Budget Sign-Off Flag Is Structurally Undermined

The executive summary flags SMS budget as requiring explicit sign-off before finalization. But Section 1.1 already commits to specific SMS volume (~75K/day) and Section 3.4 is cut off mid-sentence. The design has already made SMS architectural commitments contingent on a budget approval that hasn't happened. If the budget is rejected or constrained, the volume estimates and the per-channel queue justification (which partly rests on SMS/OTP isolation) are affected.

### 6. The Preference Cache Staleness Disclosure Is Inconsistent with the Race Condition

The document says acceptable staleness is "up to 60 seconds" and instructs disclosing this in the UI. But the race condition described — where a reader populates the cache just before a write — means staleness can be up to 60 seconds *after the invalidation fires*, not 60 seconds from the write. In the worst case (reader caches stale data 1ms before write, invalidation fires, reader's fresh-TTL entry survives), staleness is the full 60-second TTL regardless of when the user changed their preference. The UI disclosure is accurate but the document presents this as a narrow edge case when it's actually the common case for any user who changes preferences during active notification routing.

### 7. The DAU/MAU Ratio Is Assumed but Never Justified

The entire volume model rests on DAU = 3M from MAU = 10M, a 30% ratio. This is used to size push workers, in-app workers, and the planning basis. For a new social app at 10M MAU, 30% DAU/MAU is on the optimistic end — many apps in this category run 15–20%. A 15% DAU ratio halves the push and in-app volume estimates, which changes the worker sizing and potentially the cost justification for per-channel queue complexity. The model presents this as a given rather than a variable with its own sensitivity analysis.

### 8. The APNs 410 Token Retention Logic Creates a Correctness Hazard

The document correctly notes that tokens registered *after* Apple's provided timestamp should not be purged. But the implementation stores only `is_valid` and `invalidated_reason` — there is no `invalidated_at` timestamp stored on the token record. The nightly purge job therefore cannot implement the "registered after invalidation timestamp" check. The data model doesn't support the stated logic.

### 9. The Calibration Checkpoint Threshold Is Arbitrary and Possibly Too Late

The ±40% threshold for the Month 2 calibration checkpoint is presented without justification. More importantly, Month 2 is when the "working system" is first deployed — meaning there may be only days of production data before the checkpoint. If actual volume is 2× planning basis (within the aggressive scenario the document explicitly considers), the checkpoint fires, but the team is already committed to Month 3 scope. The checkpoint is described as "revisit worker sizing" but there's no defined decision process, owner, or criteria for what constitutes an acceptable response.