# Graph Report - C:\Users\tombl\Documents\Codex\2026-08-23\thi\foil-persona-validation  (2026-08-28)

## Corpus Check
- 274 files · ~235,453 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 5167 nodes · 14558 edges · 230 communities (201 shown, 29 thin omitted)
- Extraction: 76% EXTRACTED · 24% INFERRED · 0% AMBIGUOUS · INFERRED: 3434 edges (avg confidence: 0.6)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `38ddc6ab`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Code Community 0
- Code Community 1
- Code Community 2
- Code Community 3
- Code Community 4
- Code Community 5
- Code Community 6
- Code Community 7
- Code Community 8
- Code Community 9
- Code Community 10
- Code Community 11
- Code Community 12
- Code Community 13
- Code Community 14
- Code Community 15
- Code Community 16
- Code Community 17
- Code Community 18
- Code Community 19
- Code Community 20
- Code Community 21
- Code Community 22
- Code Community 23
- Code Community 24
- Code Community 25
- Code Community 26
- Code Community 27
- Code Community 28
- Code Community 29
- Code Community 30
- Code Community 31
- Code Community 32
- Code Community 33
- Code Community 34
- Code Community 35
- Code Community 36
- Code Community 37
- Code Community 38
- Code Community 39
- Code Community 40
- Code Community 41
- Code Community 42
- Code Community 43
- Code Community 44
- Code Community 45
- Code Community 46
- Code Community 47
- Code Community 48
- Code Community 49
- Code Community 50
- Code Community 51
- Code Community 52
- Code Community 53
- Code Community 54
- Code Community 55
- Code Community 56
- Code Community 57
- Code Community 58
- Code Community 59
- Code Community 60
- Code Community 61
- Code Community 62
- Code Community 63
- Code Community 64
- Code Community 65
- Code Community 66
- Code Community 67
- Code Community 68
- Code Community 69
- Code Community 70
- Code Community 71
- Code Community 72
- Code Community 73
- Code Community 74
- Code Community 75
- Code Community 76
- Code Community 77
- Code Community 78
- Code Community 79
- Code Community 80
- Code Community 81
- Code Community 82
- Code Community 83
- Code Community 84
- Code Community 85
- Code Community 86
- Code Community 87
- Code Community 88
- Code Community 89
- Code Community 90
- Code Community 91
- Code Community 92
- Code Community 93
- Code Community 94
- Code Community 95
- Code Community 96
- Code Community 97
- Code Community 98
- Code Community 99
- Code Community 100
- Code Community 101
- Code Community 102
- Code Community 103
- Code Community 104
- Code Community 105
- Code Community 106
- Code Community 107
- Code Community 108
- Code Community 109
- Code Community 110
- Code Community 111
- Code Community 112
- Code Community 113
- Code Community 114
- Code Community 115
- Code Community 116
- Code Community 117
- Code Community 118
- Code Community 119
- Code Community 120
- Code Community 121
- Code Community 122
- Code Community 123
- Code Community 124
- Code Community 125
- Code Community 126
- Code Community 127
- Code Community 128
- Code Community 129
- Code Community 130
- Code Community 131
- Code Community 132
- Code Community 133
- Code Community 134
- Code Community 135
- Code Community 136
- Code Community 137
- Code Community 138
- Code Community 139
- Code Community 140
- Code Community 141
- Code Community 142
- Code Community 143
- Code Community 144
- Code Community 145
- Code Community 146
- Code Community 147
- Code Community 148
- Code Community 149
- Code Community 150
- Code Community 151
- Code Community 152
- Code Community 153
- Code Community 154
- Code Community 155
- Code Community 156
- Code Community 157
- Code Community 158
- Code Community 159
- Code Community 160
- Code Community 161
- Code Community 162
- Code Community 163
- Code Community 164
- Code Community 165
- Code Community 166
- Code Community 167
- Code Community 168
- Code Community 169
- Code Community 170
- Code Community 171
- Code Community 172
- Code Community 173
- Code Community 174
- Code Community 175
- Code Community 176
- Code Community 177
- Code Community 178
- Code Community 179
- Code Community 180
- Code Community 181
- Code Community 182
- Code Community 183
- Code Community 184
- Code Community 185
- Code Community 186
- Code Community 187
- Code Community 188
- Code Community 189
- Code Community 190
- Code Community 191
- Code Community 192
- Code Community 193
- Code Community 194
- Code Community 195
- Code Community 196
- Code Community 197
- Code Community 198
- Code Community 199
- Code Community 200
- Code Community 201
- Code Community 202
- Code Community 203
- Code Community 204
- Code Community 205
- Code Community 206
- Code Community 207
- Code Community 208
- Code Community 209
- Code Community 210
- Code Community 211
- Code Community 212
- Code Community 213
- Code Community 214
- Code Community 215
- Code Community 216
- Code Community 217
- Code Community 218
- Code Community 219
- Code Community 220
- Code Community 221
- Code Community 222
- Code Community 223
- Code Community 224
- Code Community 225
- Code Community 226

## God Nodes (most connected - your core abstractions)
1. `RuntimeStore` - 130 edges
2. `ImmutableBindings` - 68 edges
3. `Receipt` - 68 edges
4. `SignalAuthority` - 64 edges
5. `Verdict` - 62 edges
6. `RuntimePolicyV2` - 57 edges
7. `Route` - 51 edges
8. `BenchmarkTokenLedger` - 50 edges
9. `EvidenceClass` - 49 edges
10. `TaskContext` - 49 edges

## Surprising Connections (you probably didn't know these)
- `ProtocolError` --uses--> `VerificationStatus`  [INFERRED]
  benchmarks/harness/foil_adaptive_two_benchmark_pilot.py → tools/egrt_verifiers.py
- `ProtocolError` --uses--> `AdaptiveRoutePolicy`  [INFERRED]
  benchmarks/harness/foil_adaptive_two_benchmark_pilot.py → tools/foil_adaptive_route.py
- `ProtocolError` --uses--> `FrozenEVModel`  [INFERRED]
  benchmarks/harness/foil_adaptive_two_benchmark_pilot.py → tools/foil_adaptive_route.py
- `ProtocolError` --uses--> `RiskClass`  [INFERRED]
  benchmarks/harness/foil_adaptive_two_benchmark_pilot.py → tools/foil_adaptive_route.py
- `ProtocolError` --uses--> `Route`  [INFERRED]
  benchmarks/harness/foil_adaptive_two_benchmark_pilot.py → tools/foil_adaptive_route.py

## Import Cycles
- None detected.

## Communities (230 total, 29 thin omitted)

### Community 0 - "Code Community 0"
Cohesion: 0.06
Nodes (82): answer_schema(), build_argv(), build_manifest(), call_count(), canonical_json(), codex_executable(), codex_version(), execute_call() (+74 more)

### Community 1 - "Code Community 1"
Cohesion: 0.07
Nodes (63): _base_receipt(), build_argv(), build_manifest(), build_requests_document(), canonical(), cmd_prepare(), cmd_run(), cmd_score() (+55 more)

### Community 2 - "Code Community 2"
Cohesion: 0.10
Nodes (49): build_predictions(), run_predictions(), RetrievalRunner, SmartToolRuntimeTests, task(), QuestionOnlyTask, build_calibrated_runtime_policy(), Wire a target calibration into the active runtime without exploration. (+41 more)

### Community 3 - "Code Community 3"
Cohesion: 0.05
Nodes (40): CouncilGateTests, FoilBridgeGateTests, HookGateTests, init_root(), ModuleInvariantGuards, PowerGateTests, Path, Regression gate tests for the P0 typed-runtime repairs. Each test's docstring… (+32 more)

### Community 4 - "Code Community 4"
Cohesion: 0.10
Nodes (71): answer_schema(), build_argv(), build_lock(), build_manifest(), build_units(), call_count(), canonical_json(), codex_executable() (+63 more)

### Community 5 - "Code Community 5"
Cohesion: 0.07
Nodes (71): build_argv(), build_manifest(), build_prompt(), build_unit_plan(), child_env(), cmd_check_only(), cmd_prepare(), cmd_run() (+63 more)

### Community 6 - "Code Community 6"
Cohesion: 0.09
Nodes (42): RuntimePolicyTaskEvidenceTests, RPSRuntimePolicyWiringTests, ComplementKind, EffortMode, EvidenceDirection, policy_trace(), PolicyAction, PolicyDecision (+34 more)

### Community 7 - "Code Community 7"
Cohesion: 0.07
Nodes (39): ClaimKind, digest(), FoilP1MechanismTests, AcquisitionObservation, AcquisitionProposal, AcquisitionReceipt, ChallengerCandidate, ChallengerReceipt (+31 more)

### Community 8 - "Code Community 8"
Cohesion: 0.08
Nodes (35): AdaptiveRouteTests, compiled(), d(), ev(), HostDeclaredRouteTests, task_spec(), AdaptiveRoutePolicy, CapabilityPosterior (+27 more)

### Community 9 - "Code Community 9"
Cohesion: 0.09
Nodes (34): d(), eligibility(), observation(), ShadowRouteLedgerTests, vector(), Return exact EV numerator with denominator ``PPM_SQUARED``., Route, AssignmentDesign (+26 more)

### Community 10 - "Code Community 10"
Cohesion: 0.08
Nodes (34): d(), ReplayGuardTests, AuthorityReplayGuard, One-use replay guard for host-consumed FOIL authority tokens., Consume a valid authority nonce once within one host process. Durable hosts…, AuthorityIssuer, AuthorityToken, CandidateBinding (+26 more)

### Community 11 - "Code Community 11"
Cohesion: 0.12
Nodes (39): _statuses(), ScannerBindingTests, bindings(), diagnostic(), plan(), ResidualScannerTests, bindings(), report() (+31 more)

### Community 12 - "Code Community 12"
Cohesion: 0.08
Nodes (13): CouncilTests, GauntletTests, init_root(), LedgerTests, MeditateTests, MindTests, PowerTests, Path (+5 more)

### Community 13 - "Code Community 13"
Cohesion: 0.08
Nodes (27): plan(), ToolPlanV2Tests, build_plan_catalog(), choose_plan(), ContinuationDecision, ContinuationEvidence, _count(), decide_incremental_query() (+19 more)

### Community 14 - "Code Community 14"
Cohesion: 0.10
Nodes (19): _all_artifacts(), BlackGemTestCase, breakers(), CanaryTests, constant(), DesignHardeningTests, FoilRoutingTests, init_root() (+11 more)

### Community 15 - "Code Community 15"
Cohesion: 0.11
Nodes (26): capsule(), digest(), observation(), Invariant tests for the default-off RPS v0.6.1 shadow controller., RPSShadowControllerTests, Evaluate RPS only through an explicitly admitted shadow action., assess_check(), CheckAssessment (+18 more)

### Community 16 - "Code Community 16"
Cohesion: 0.11
Nodes (48): activate(), active_name(), bootstrap_active(), classify(), compact_context(), _count(), derive_tier(), _domain_lines() (+40 more)

### Community 17 - "Code Community 17"
Cohesion: 0.14
Nodes (48): audit(), base_prompt_for(), build_argv(), build_manifest(), build_results(), build_units(), canonical(), check() (+40 more)

### Community 18 - "Code Community 18"
Cohesion: 0.12
Nodes (29): calibration(), checks(), d(), digest_for(), ev_model(), FormalizationAdmissionTests, IntegratedPipelineTests, policy() (+21 more)

### Community 19 - "Code Community 19"
Cohesion: 0.12
Nodes (32): development_gate_result(), binding(), d(), evidence(), plan(), PromotionGateTests, Tests for deterministic external FOIL gate evaluation., Gate (+24 more)

### Community 20 - "Code Community 20"
Cohesion: 0.08
Nodes (19): D1AcceptanceTests, MigrationTests, ObservationRecordingTests, ProfileTestCase, Path, Profile schema v2: verification, execution ownership, and the v1 migration. v1…, Fail closed: withhold the claim rather than invent independence., The exact defect patch-001 closes, at 50x the volume it needed. (+11 more)

### Community 21 - "Code Community 21"
Cohesion: 0.09
Nodes (42): record_control(), main(), Status/event CLI for the typed Evidence-Governed Research Toolkit runtime., new_id(), utcnow(), _active_task(), _adaptation_obligations(), main() (+34 more)

### Community 22 - "Code Community 22"
Cohesion: 0.10
Nodes (32): AnswerPayload, approval(), d(), direct_request(), evidence_certificate(), full_pipeline_request(), HostFinalizerTests, Tests for the explicit, fail-closed host finalization boundary. (+24 more)

### Community 23 - "Code Community 23"
Cohesion: 0.10
Nodes (27): ContextRenderer, ProfileLoader, RequirementRouter, FoilActivationMonitorTests, profile_loader(), ActivationDecision, ActivationEvent, ActivationOutcome (+19 more)

### Community 24 - "Code Community 24"
Cohesion: 0.07
Nodes (24): AssistanceVocabularyTests, ContractDriftTests, ExecutionOwnerTests, D3, D8 - one assistance/ownership vocabulary for the contract and the runtime., The documented contract and the runtime cannot drift apart silently., Ordinals are contract data; reordering silently rewrites history., Assistance intensity and execution ownership are different axes., Assistance (+16 more)

### Community 25 - "Code Community 25"
Cohesion: 0.09
Nodes (24): main(), Path, Freeze and score question-only FOIL route-opportunity predictions. Prediction…, _read_json(), _write_json(), ClosedQuestionInputTests, FrozenArtifactTests, build_prediction_artifact() (+16 more)

### Community 26 - "Code Community 26"
Cohesion: 0.18
Nodes (41): answer_schema(), audit(), build_manifest(), build_results(), canonical_json(), check(), common_task(), configure_executor() (+33 more)

### Community 27 - "Code Community 27"
Cohesion: 0.12
Nodes (25): CalibrationEvidenceTests, calibration(), context(), datetime, registration(), ResidualAuthorityTests, Applicability, Trusted registration; a sensor report cannot alter these fields. (+17 more)

### Community 28 - "Code Community 28"
Cohesion: 0.11
Nodes (35): CrossCritique, canonical_json(), digest(), EvidenceClass, EvidenceRef, Obligation, _plain(), Any (+27 more)

### Community 29 - "Code Community 29"
Cohesion: 0.18
Nodes (40): answer_schema(), audit(), build_manifest(), build_results(), canonical_json(), check(), common_task(), configure_executor() (+32 more)

### Community 30 - "Code Community 30"
Cohesion: 0.10
Nodes (27): DeterministicVerifierTests, _bounded_certified(), _canonical_rational(), _certified_arithmetic_equality(), _certified_expression_value(), _certified_fraction_value(), DeterministicVerifierRegistry, _digest_exact() (+19 more)

### Community 31 - "Code Community 31"
Cohesion: 0.14
Nodes (31): assert_disjoint_partitions(), AtlasError, _compiler_rows(), _domain_summary(), DomainSummary, load_atlas(), main(), _mapping() (+23 more)

### Community 32 - "Code Community 32"
Cohesion: 0.12
Nodes (24): bindings(), coverage(), EvidenceCertificateTests, CoverageTests, requirement(), complete_coverage(), coverage(), bindings() (+16 more)

### Community 33 - "Code Community 33"
Cohesion: 0.14
Nodes (37): apportion_usage(), audit(), call_model(), canonical(), _closed_items(), codex_executable(), compare_prompt(), constructor_prompt() (+29 more)

### Community 34 - "Code Community 34"
Cohesion: 0.19
Nodes (38): answer_schema(), assert_sources(), audit(), build_manifest(), build_results(), canonical_json(), check(), configure_executor() (+30 more)

### Community 35 - "Code Community 35"
Cohesion: 0.12
Nodes (22): Tests for the digest-only explicit host-action request bridge., authority(), bindings(), certificate(), external(), Safety contracts for externally supplied FOIL shadow repair references., ShadowRepairTests, AdmissionDecision (+14 more)

### Community 36 - "Code Community 36"
Cohesion: 0.11
Nodes (28): FoilAssessmentTests, _forbidden_key(), patch-002: item identity survives into the report., A perfect two-item-per-domain screen is SCREEN-tier evidence only. Previously…, answer(), apply_to_profile(), build(), _causal() (+20 more)

### Community 37 - "Code Community 37"
Cohesion: 0.11
Nodes (22): AssistancePolicyTests, advance_assistance_floor(), AssistanceDecision, AssistanceIntent, AssistanceReason, _classification(), _enum(), _next_assistance() (+14 more)

### Community 38 - "Code Community 38"
Cohesion: 0.10
Nodes (17): EvidenceContractTests, canonical_fraction(), ComputationBinding, _count(), _evaluate(), EvidenceDocument, EvidenceSpan, _fraction() (+9 more)

### Community 39 - "Code Community 39"
Cohesion: 0.10
Nodes (26): _detected(), StructuredProvenanceVerifierTests, _claim_count_key(), ClaimBundle, compile_task_spec(), _digest(), _enum(), _load_json() (+18 more)

### Community 40 - "Code Community 40"
Cohesion: 0.12
Nodes (25): aggregate_replicates(), binom_pmf(), condition_summary(), exact_mcnemar_two_sided(), load_jsonl(), main(), mean_or_none(), median_or_none() (+17 more)

### Community 41 - "Code Community 41"
Cohesion: 0.15
Nodes (23): development_study_result(), d(), inventory(), LaterStudyContractTests, plan(), Tests for the fail-closed later-study contracts., _cell_name(), _digest() (+15 more)

### Community 42 - "Code Community 42"
Cohesion: 0.15
Nodes (35): _artifact_path(), artifact_ref(), Breaker, BreakTriple, _call(), CanaryProbe, create_strike(), _delimited() (+27 more)

### Community 43 - "Code Community 43"
Cohesion: 0.14
Nodes (28): build_receipt(), Decision, default_receipt_path(), _digest(), exact_two_sided(), iter_profiles(), iter_tasks(), load_policy() (+20 more)

### Community 44 - "Code Community 44"
Cohesion: 0.12
Nodes (19): build_report(), main(), _mapping(), _object(), Path, Build the target-derived FOIL calibration report from frozen artifacts., SmartToolCalibrationTests, assess_historical_route() (+11 more)

### Community 45 - "Code Community 45"
Cohesion: 0.13
Nodes (30): Observation, One performance event. `correct` is the outcome. `tier` decides admissibility…, _bundle_for(), CapabilityEvidence, _coerce_bundle(), _compatible_observations(), complement_for_capability(), _meets_level() (+22 more)

### Community 46 - "Code Community 46"
Cohesion: 0.11
Nodes (18): GeneratedDiscoveryEnvelope, _binding(), CertifiedLanguageSeparationTests, _digest(), _envelope(), _receipt(), _request(), RuleBankBoundaryTests (+10 more)

### Community 47 - "Code Community 47"
Cohesion: 0.14
Nodes (17): complete_ledger(), Adversarial contract tests for the FOIL v5 sealed run ledger., RunLedgerTests, _canonical_json(), _digest(), LedgerError, Any, ValueError (+9 more)

### Community 48 - "Code Community 48"
Cohesion: 0.18
Nodes (29): manifest(), protocol(), ShadowRuntimeTests, _authority(), _bindings(), _cases(), _claim(), _contributions() (+21 more)

### Community 49 - "Code Community 49"
Cohesion: 0.11
Nodes (31): _betacf(), classify(), _effective_counts(), EvidencePolicy, EvidenceTier, false_classification_rates(), _freshest_load_bearing_age_days(), items_for_target_error() (+23 more)

### Community 50 - "Code Community 50"
Cohesion: 0.14
Nodes (33): _admissible_transfer(), _assistance_is_a0(), _assistance_label(), _blocked(), _changed_context(), _costs(), _digest(), _feedback_categories() (+25 more)

### Community 51 - "Code Community 51"
Cohesion: 0.21
Nodes (32): buildFarField(), buildWeb(), clamp(), diamond(), drawFar(), drawGem(), drawHero(), drawMind() (+24 more)

### Community 52 - "Code Community 52"
Cohesion: 0.13
Nodes (11): contract(), ToolContractTests, EvidenceEnvelope, _https_url(), _non_negative_int(), _positive_int(), Closed contracts and evidence receipts for bounded FOIL tool execution. This…, _sha256() (+3 more)

### Community 53 - "Code Community 53"
Cohesion: 0.13
Nodes (23): VerifierResult, FrozenEVModel, Frozen, externally estimated route values in fixed-point units. Probabilities…, RiskClass, ShadowRouteDecision, AdmittedCompiledTaskSpec, AdmittedShadowRouteDecision, decide_admitted_shadow_route() (+15 more)

### Community 54 - "Code Community 54"
Cohesion: 0.14
Nodes (30): _anthropic_messages(), _cli(), complete(), _digest(), _mock(), ModelError, ModelResponse, ModelSpec (+22 more)

### Community 55 - "Code Community 55"
Cohesion: 0.15
Nodes (23): _arc_records(), _association(), _canonical_answer(), evaluate_records(), _fetch(), _gpqa_records(), main(), _mutant() (+15 more)

### Community 56 - "Code Community 56"
Cohesion: 0.09
Nodes (4): bundle(), observations(), P0 task-requirement -> evidence -> minimum-complement routing tests., RequirementCoverageTests

### Community 57 - "Code Community 57"
Cohesion: 0.15
Nodes (22): example_protocol(), ProtocolContractTests, Contract tests for the content-addressed FOIL v5 shadow protocol., canonical_json(), content_sha256(), ProtocolValidationError, Any, ValueError (+14 more)

### Community 58 - "Code Community 58"
Cohesion: 0.09
Nodes (10): Positive control for every truncation case below., C1 - the chain alone cannot see events removed from its end. Deleting the last…, The determined version: trim, then fix the two tip fields to match. The chain…, A refusal and a broker journal row both carry `operation`. Counting either…, 12 threads against a budget of 5 grant exactly 5. This is the test the O_EXCL…, A transport failure must refund the hold rather than burn a query., Positive control for the refund: the same failure minus the refund., The hook process holds the digest, never the prompt text. (+2 more)

### Community 59 - "Code Community 59"
Cohesion: 0.14
Nodes (30): add_gap(), add_intervention(), add_outcome(), _admissible(), _changed_context_proof(), _confidence(), _content_id(), gap_kinds_contract_block() (+22 more)

### Community 60 - "Code Community 60"
Cohesion: 0.17
Nodes (16): Runner, AdaptiveExecutorTests, d(), decision(), ActiveRouteReceipt, BenchmarkExecutionPolicy, execute_benchmark_route(), ExecutionAction (+8 more)

### Community 61 - "Code Community 61"
Cohesion: 0.11
Nodes (14): main(), _policy(), Sealed zero-provider pilot for FOIL's evidence-closed benchmark path., run_predictions(), score_predictions(), main(), _object(), Path (+6 more)

### Community 62 - "Code Community 62"
Cohesion: 0.19
Nodes (28): build_manifest(), _canonical(), _condition_metrics(), digest(), _load_json(), main(), _observation(), _parse_time() (+20 more)

### Community 63 - "Code Community 63"
Cohesion: 0.17
Nodes (17): d(), event(), PostSolveMonitorTests, evaluate_postsolve_event(), PostSolveAction, PostSolveCursor, PostSolveDecision, PostSolveEvent (+9 more)

### Community 64 - "Code Community 64"
Cohesion: 0.14
Nodes (22): _digest(), _evaluate(), HostTaskType, JsonPrimitive, _parse_json_object(), _primitive_matches(), Enum, str (+14 more)

### Community 65 - "Code Community 65"
Cohesion: 0.13
Nodes (17): bindings(), ClaimCompilerTests, ClaimCompilation, ClaimKind, ClaimOutcome, classify_outcome(), compile_claim(), PostSolveClaim (+9 more)

### Community 66 - "Code Community 66"
Cohesion: 0.14
Nodes (15): digest(), Contract tests for the RPS v0.6.2 paired scorer., row(), RPSV062ScorerTests, trace(), check_commitment_digest(), _optional_digest(), Enum (+7 more)

### Community 67 - "Code Community 67"
Cohesion: 0.14
Nodes (12): base_env(), BrokerTestCase, BudgetEnforcementTests, InactiveBrokerTests, D6 - the PreToolUse broker, the point where a frozen-run budget is enforced.…, FOIL_TASK_RUN is the single switch: unset means no run was intended., Without this, 'inert' could just mean 'the hook never works'., The reason is only true because no capability declares writes=True. (+4 more)

### Community 68 - "Code Community 68"
Cohesion: 0.18
Nodes (11): _integrity_body(), Any, Path, Private, config-aware state and content-addressed receipt storage. Mutable…, Advisory lock scoped to this store, for read-modify-write cycles., Monotonic per-store sequence number. Wall-clock timestamps tie on Windows for…, _receipt_order(), RuntimeStore (+3 more)

### Community 69 - "Code Community 69"
Cohesion: 0.10
Nodes (9): ConstructorReceipt, ConstructorRunner, Run at most one blind constructor pass and validate its complete draft., run_bounded_constructor(), _validate_total_use(), CandidateAnswer, ComputationReceipt, EvidencePacket (+1 more)

### Community 70 - "Code Community 70"
Cohesion: 0.12
Nodes (9): ClaudeJsonParserTests, CliDeliveryTests, Model layer — any LLM through configuration rather than code. The…, A `cli` model whose command is a throwaway Python script., `output_parser: claude_json` — read the envelope, or fail loudly., The parser reports the failure; it does not decide what to do about it. Whether…, An envelope may flag an error while still reporting subtype "success". This is…, No vendor flag logic in the adapter: knobs are argv, `{model}` substitutes. (+1 more)

### Community 71 - "Code Community 71"
Cohesion: 0.14
Nodes (19): Annotation, candidate_pack(), candidate_rows(), _canonical_number(), _different_operator(), evaluate_expression(), expression_numbers(), final_value() (+11 more)

### Community 72 - "Code Community 72"
Cohesion: 0.17
Nodes (18): certificate(), CertificateClass, EvidenceCertificate, _legacy_status(), Enum, str, Claim-bound evidence certificates and safe adapters to legacy admission types., Adapt only structural certificates; incomplete scope remains unknown. (+10 more)

### Community 73 - "Code Community 73"
Cohesion: 0.15
Nodes (18): EvidencePlanRunner, Enum, str, Pure symmetric A0/B selection for evidence-closed FOIL benchmarks., Select B only after a strict, symmetric evidence preference., select_answer(), SelectionOutcome, SelectionReceipt (+10 more)

### Community 74 - "Code Community 74"
Cohesion: 0.27
Nodes (10): check(), digest(), host(), Invariant tests for host-verifier-first RPS v0.6.2., rival(), RPSV062ControllerTests, RPSV062RuntimePolicyTests, evaluate_rps_v062_shadow() (+2 more)

### Community 75 - "Code Community 75"
Cohesion: 0.28
Nodes (23): build_parser(), cmd_add(), cmd_capabilities(), cmd_detect(), cmd_doctor(), cmd_init(), cmd_list(), cmd_probe() (+15 more)

### Community 76 - "Code Community 76"
Cohesion: 0.15
Nodes (16): HTMLParser, _SafeRedirect, _TextExtractor, ConstructorDraft, ConstructorOutcome, ConstructorPolicy, _count(), Enum (+8 more)

### Community 77 - "Code Community 77"
Cohesion: 0.16
Nodes (17): _audit_rows(), _average_ranks(), build_report(), _canonical_digest(), generator_report(), _lift(), _localization(), _pct() (+9 more)

### Community 78 - "Code Community 78"
Cohesion: 0.13
Nodes (7): ExecutionOwnershipTests, InterventionLedgerTests, D3, D4 - the complement/intervention ledger., Positive control: the same input minus the ownership mutation passes., v1 returned NO_VERIFIED_OUTCOME for the documented A0 label., v1 returned TRANSFER_OBSERVED for one old pass and five later fails., A tool-executed pass is task evidence, never ownership evidence.

### Community 79 - "Code Community 79"
Cohesion: 0.09
Nodes (9): AdapterMapTests, ExhaustiveInvariantTests, Exhaustive enumeration of the bench bucket domain against the real V2 kernel.…, A reference-only run must never be mistaken for a candidate run., One enumeration, many assertions., The bucket -> kernel map is the only bridge; pin the load-bearing parts., The map is derived from V2's own thresholds, not invented., This is what keeps I08/I09 honest - see the harness docstring. If a synthesised… (+1 more)

### Community 80 - "Code Community 80"
Cohesion: 0.21
Nodes (11): digest(), HostVerifierTests, Tests for answer-blind deterministic RPS Stage 1., task(), _canonical(), HostTaskDescriptor, JsonFieldSpec, Select and freeze one check without accepting an answer parameter. (+3 more)

### Community 81 - "Code Community 81"
Cohesion: 0.23
Nodes (4): FailClosedTests, PartialConfigurationTests, A set FOIL_TASK_RUN asserts a run is in progress; a broken one fails closed.…, An unbudgeted tool is guarded by nothing anyway. Refusing `Read` because the…

### Community 82 - "Code Community 82"
Cohesion: 0.21
Nodes (20): commit(), commitment_digest(), CouncilSeat, CouncilState, create_council(), _cross_critique_complete(), finalize(), _jaccard() (+12 more)

### Community 83 - "Code Community 83"
Cohesion: 0.21
Nodes (20): _affine(), _affine_expression(), ArithmeticRuleBankEnvelope, _binding(), _bounded(), _claim(), discover_arithmetic_rule_bank(), _empty_counts() (+12 more)

### Community 84 - "Code Community 84"
Cohesion: 0.20
Nodes (22): _auto_mode(), _available_context(), build_payload(), _canonical_requirements(), _continuation_lease(), _emit(), _frozen_binding(), _input() (+14 more)

### Community 85 - "Code Community 85"
Cohesion: 0.18
Nodes (20): apply_exclusions(), family_results(), holm(), mcnemar_exact(), mcnemar_exact_fraction(), paired_binary(), PairedBinaryObservation, PairedBinaryPlan (+12 more)

### Community 86 - "Code Community 86"
Cohesion: 0.15
Nodes (4): d(), FrozenPilotTests, item(), valid_receipt()

### Community 87 - "Code Community 87"
Cohesion: 0.13
Nodes (7): BenchmarkTokenLedgerTests, BenchmarkBudgetError, BenchmarkTokenLedger, RuntimeError, Fail-closed provider-token reservations for paid FOIL benchmarks. The ledger…, A benchmark call cannot be launched within the hard token envelope., TokenReservation

### Community 88 - "Code Community 88"
Cohesion: 0.11
Nodes (12): SignalAuthorityTests, admit_competence_observation(), EvidenceAdmissionError, may_satisfy_factual_obligation(), Enum, ValueError, Typed boundary between FOIL control signals and admissible evidence. Routing…, Raised when a control signal is presented as admitted evidence. (+4 more)

### Community 89 - "Code Community 89"
Cohesion: 0.16
Nodes (8): DryRunTests, ExecutionTests, quiet(), Shared fixture: a temp run directory, a temp guard directory, a fake `claude`., Guards against drift in `foil_models._cli`'s message rendering. The adapter…, The case a subtype-only check misses. The envelope reports subtype "success"…, Swallow the harness's progress output so test output stays readable., _RunHarness

### Community 90 - "Code Community 90"
Cohesion: 0.22
Nodes (15): _adjudication(), build_report(), _canonical_digest(), main(), Path, row_digest(), _score(), _source_manifest() (+7 more)

### Community 91 - "Code Community 91"
Cohesion: 0.13
Nodes (9): DecayFloorTests, FreshnessGateTests, Evidence at the decay floor cannot decide, in either direction. `min_weight` is…, D4 - a verdict requires one load-bearing observation inside the horizon. Decay…, Regression: this exact input classified as POSSIBLE_GAP before the gate., Negative control: the gate, not the input, is what withholds the verdict., Positive control: the same ancient pile decides once anything is fresh., Old evidence is downweighted, not discarded, when the gate is open. (+1 more)

### Community 92 - "Code Community 92"
Cohesion: 0.23
Nodes (19): Annotation, MutationAttempt, _attempt(), attempt_all(), conservation(), _consistent_global(), _consistent_local(), _drop_step() (+11 more)

### Community 93 - "Code Community 93"
Cohesion: 0.20
Nodes (19): association(), _average_ranks(), build_report(), evaluate_answer(), independently_verify_report(), main(), _parser(), _pearson() (+11 more)

### Community 94 - "Code Community 94"
Cohesion: 0.17
Nodes (14): cluster_base_items(), ClusteredOutcome, _confidence(), _count(), Base-item-clustered descriptive statistics for offline FOIL v5 Gate-1 runs.…, Report recall/FPR/PPV over clustered base answers and all raw statuses., Return a two-sided Wilson interval; no observations remains undefined., Collapse variants conservatively: any flag is a flag for its base item. (+6 more)

### Community 95 - "Code Community 95"
Cohesion: 0.15
Nodes (6): ProfileSignal, Ported V2 kernel tests. Source: `tests/test_foil_vnext_v2.py` at `9540860`…, RuntimePolicyV2Tests, strong_gap(), LoadBearingUncertainty, An unresolved fact/check that could change the final answer.

### Community 96 - "Code Community 96"
Cohesion: 0.20
Nodes (6): CandidateStateModelTests, digest(), Exhaustive small-model checks for the pure promotion transition., D4 - later verified evidence outranks stale evidence., RecencyTests, timedelta

### Community 97 - "Code Community 97"
Cohesion: 0.17
Nodes (13): bindings(), V5ScoreTests, ActionConditionedScore, ActionOutcome, _count(), DeclaredCoverageScore, Enum, str (+5 more)

### Community 98 - "Code Community 98"
Cohesion: 0.23
Nodes (17): _Annotation, _annotations(), _binding(), _claim(), DiscoveryEnvelope, _envelope(), _number(), _operands() (+9 more)

### Community 99 - "Code Community 99"
Cohesion: 0.16
Nodes (13): build_report(), main(), _mapping(), Path, Calibrate RPS Stage 1 and no-tools model interjection from frozen receipts., _read(), _rows(), calibrate_rps_interjection() (+5 more)

### Community 100 - "Code Community 100"
Cohesion: 0.19
Nodes (11): RegistrationBoundaryTests, AdmissionState, AuthorityAction, AuthorityCeiling, CandidateRepair, CheckStatus, EvidenceSurface, Enum (+3 more)

### Community 101 - "Code Community 101"
Cohesion: 0.37
Nodes (10): candidate(), evidence(), RetrievalClaimComparatorTests, AtomicClaim, QuestionObligation, ComparatorPolicy, compare_candidate(), SemanticComparator (+2 more)

### Community 102 - "Code Community 102"
Cohesion: 0.32
Nodes (9): check(), digest(), host(), Fail-closed tests for benchmark-active RPS v0.6.3., rival(), RPSV063Tests, evaluate_verified_correction(), Select B only under contradicted-A/confirmed-B host evidence. (+1 more)

### Community 103 - "Code Community 103"
Cohesion: 0.32
Nodes (18): _adversarial_domain_probe(), build_plan(), _classification(), deep_context(), _domain_probe(), ensure_deep(), _facet_row(), main() (+10 more)

### Community 104 - "Code Community 104"
Cohesion: 0.23
Nodes (18): _atomic_save(), close(), _commit(), _exclusive_lockfile(), exclusive_state_lock(), guarded_operation(), load(), main() (+10 more)

### Community 105 - "Code Community 105"
Cohesion: 0.23
Nodes (18): action_loop(), _as_fingerprint(), evaluate(), fingerprint_similarity(), _incident_key(), load_state(), main(), message_fingerprint() (+10 more)

### Community 106 - "Code Community 106"
Cohesion: 0.18
Nodes (13): build_report(), _completed_items(), _contains_token(), main(), Path, _query_strings(), Zero-token audit of the four historical HLE tool-arm rescue traces. This audit…, _read_events() (+5 more)

### Community 107 - "Code Community 107"
Cohesion: 0.16
Nodes (17): _binom_cdf(), _binom_pmf(), discordance(), exact_mcnemar(), holm_adjust(), midp_mcnemar(), paired_report(), Any (+9 more)

### Community 108 - "Code Community 108"
Cohesion: 0.35
Nodes (7): candidate(), CandidateAdmissionTests, certificate(), Adversarial tests for FOIL's shadow-only authority/admission kernel. These…, semantic(), decide_admission(), Gate a candidate without applying it; COMMITTABLE still requires a host.

### Community 109 - "Code Community 109"
Cohesion: 0.19
Nodes (15): D5 - declared capability attributes must actually govern routing., capability_names(), capability_writes(), Authoritative FOIL capability and claim-routing registry. This is intentionally…, Can this capability semantically perform an external write?, validate_registry(), CapabilityWriteError, main() (+7 more)

### Community 110 - "Code Community 110"
Cohesion: 0.16
Nodes (10): ContractAuditTests, audit(), audit_document(), _closed(), _digest_bytes(), _headings(), main(), Path (+2 more)

### Community 111 - "Code Community 111"
Cohesion: 0.24
Nodes (8): DiscoveryBoundaryTests, request(), _digest(), ProvenanceV2BoundaryTests, _request(), discover_obligations(), DiscoveryPolicy, Discover only the narrow annotated-arithmetic execution class, default off.

### Community 112 - "Code Community 112"
Cohesion: 0.25
Nodes (13): AnswerKind, ClaimStatus, ClaimVerdict, ComparisonAuthority, ComparisonMethod, _computation_verdict(), _exact_span_verdict(), _normalized_text() (+5 more)

### Community 113 - "Code Community 113"
Cohesion: 0.24
Nodes (14): _append_unique(), _binding(), _canonical(), discover_obligations_v2(), DiscoveryEnvelopeV2, _envelope(), _prompt_sources(), Any (+6 more)

### Community 114 - "Code Community 114"
Cohesion: 0.18
Nodes (17): _binding(), BrokerConfigError, classify_tool(), deny(), handle(), main(), Any, RuntimeError (+9 more)

### Community 115 - "Code Community 115"
Cohesion: 0.21
Nodes (15): load_label_manifest(), select_natural_misses(), SourceResponse, candidate_pack(), candidate_rows(), load_label_manifest(), load_r16_exclusions(), load_source() (+7 more)

### Community 116 - "Code Community 116"
Cohesion: 0.33
Nodes (16): active_decision(), approve(), certificate(), compile_case(), d(), ev_model(), full_request(), main() (+8 more)

### Community 117 - "Code Community 117"
Cohesion: 0.27
Nodes (10): authority_for_defect(), run_correct_clear(), AuthorityDecisionTests, Applicability, registration(), report(), AuthorityContext, decide_authority() (+2 more)

### Community 118 - "Code Community 118"
Cohesion: 0.47
Nodes (8): constructor(), EvidenceClosedRuntimeTests, obligation(), policy(), raw_task(), retrieval_packet(), retrieval_plan(), semantic()

### Community 119 - "Code Community 119"
Cohesion: 0.19
Nodes (5): digest(), ledger(), Tests for the isolated, fail-closed FOIL P2 controllers., SelfRefineTests, TransferSelectionTests

### Community 120 - "Code Community 120"
Cohesion: 0.25
Nodes (16): answer(), apply_to_profile(), build(), infer_facets(), main(), mark_facet_relevance(), _normalize(), _options() (+8 more)

### Community 121 - "Code Community 121"
Cohesion: 0.25
Nodes (16): _as_text(), _basename(), _command_shape_allowed(), _has_sep(), _looks_like_path(), _module_args_allowed(), Any, Path (+8 more)

### Community 122 - "Code Community 122"
Cohesion: 0.28
Nodes (15): AuditError, dump(), fetch_gold(), load(), main(), normalize(), private_skill_read_counts(), Any (+7 more)

### Community 123 - "Code Community 123"
Cohesion: 0.17
Nodes (9): broker_matchers(), BrokerMatcherTests, B1 - the broker hook is only a boundary for the tools the host routes to it.…, Every PreToolUse matcher whose hooks invoke the broker script., Negative control: a matcher of `.*` would pass the test above too., The two halves agree: nothing is routed that the broker ignores., Exec form is used deliberately, and the docs say the placeholder holds.…, settings() (+1 more)

### Community 124 - "Code Community 124"
Cohesion: 0.12
Nodes (3): FoilCalibrationTests, Two verified passes used to be enough; the evidence gate is now 4.0., D2: the old two-observation gate is closed at every layer.

### Community 125 - "Code Community 125"
Cohesion: 0.17
Nodes (7): d(), MutationContractTests, NumericVerifierAndScannerTests, StatisticsAndReportTests, DiscoveryStatus, Enum, str

### Community 126 - "Code Community 126"
Cohesion: 0.37
Nodes (15): _active_task(), _event(), _explicit_aliases(), _is_error(), main(), _payload(), post_tool(), pre_tool() (+7 more)

### Community 127 - "Code Community 127"
Cohesion: 0.19
Nodes (8): _closed(), load_and_replay(), main(), _observations(), Path, Deterministic trace replay for FOIL assistance and execution ownership., replay(), AssistanceReplayTests

### Community 128 - "Code Community 128"
Cohesion: 0.17
Nodes (8): build_replay(), main(), Path, Deterministic cost/damage replays over the sealed HLE active pilot. These…, _scenario(), _sha256(), RowChoice, HLEActiveReplayTests

### Community 129 - "Code Community 129"
Cohesion: 0.27
Nodes (14): build_report(), _decision(), evaluate_answer(), frozen_candidate_rows(), independently_verify_report(), main(), _parser(), _positive_controls() (+6 more)

### Community 130 - "Code Community 130"
Cohesion: 0.13
Nodes (5): AnswerExtractionTests, CheckOnlyTests, Checks for `benchmarks/harness/claude_four_config_runner.py`. The execution…, RunnerCliTests, SettingsAndEnvironmentTests

### Community 131 - "Code Community 131"
Cohesion: 0.22
Nodes (10): aggregate_costs(), cost_per_correct(), matched_total_cost(), mean_costs(), Any, Lightweight, provider-neutral FOIL run-cost receipts. Every field is actual…, Sum each unit independently; any unavailable component stays unavailable., True only when every recorded cost unit is known and exactly matched. (+2 more)

### Community 132 - "Code Community 132"
Cohesion: 0.20
Nodes (13): llm_judge(), ask(), available(), load_keys(), main(), OpenRouterError, Any, RuntimeError (+5 more)

### Community 133 - "Code Community 133"
Cohesion: 0.26
Nodes (14): _acquire(), ensure_private_dir(), file_lock(), Path, PathLike, Restricted local persistence helpers for Gauntlet and FOIL runtime state., Apply POSIX owner-only permissions where the platform exposes them., Atomically write local state and restrict the resulting file to its owner. (+6 more)

### Community 134 - "Code Community 134"
Cohesion: 0.29
Nodes (13): _assistance_series(), _canonical(), _closed(), _digest(), _initial_observations(), load_and_run(), main(), _outcomes() (+5 more)

### Community 135 - "Code Community 135"
Cohesion: 0.29
Nodes (13): _boolean(), _count(), _digest(), load_jsonl(), main(), _mean(), _median(), paired() (+5 more)

### Community 136 - "Code Community 136"
Cohesion: 0.36
Nodes (5): d(), HostBridgeTests, create_host_action_request(), Package an admitted candidate only after consuming current ACTIVE authority.…, CandidateDecision

### Community 137 - "Code Community 137"
Cohesion: 0.32
Nodes (4): CandidateStateTests, d(), decide_candidate_state(), Return a fail-closed state without granting execution authority.

### Community 138 - "Code Community 138"
Cohesion: 0.36
Nodes (4): DittoResolverTests, manifest(), Adversarial contract tests for the bounded Ditto resolver., requirement()

### Community 139 - "Code Community 139"
Cohesion: 0.15
Nodes (3): FoilLayer2Tests, forbidden_key(), Previously asserted PROMISING_STRENGTH for a two-item-per-facet screen.

### Community 140 - "Code Community 140"
Cohesion: 0.32
Nodes (5): d(), deterministic_obligation(), ObligationCompilerTests, semantic_obligation(), spec()

### Community 141 - "Code Community 141"
Cohesion: 0.21
Nodes (14): _append_event(), attest(), authorize(), BindingMismatch, _event_digest(), prompt_hash(), Any, Append to the chain and re-anchor the state-level tip. `event_count` and `head`… (+6 more)

### Community 142 - "Code Community 142"
Cohesion: 0.26
Nodes (13): arithmetic_receipt(), exact_arithmetic(), _number(), ProofObligation, Any, AST, Fraction, Path (+5 more)

### Community 143 - "Code Community 143"
Cohesion: 0.21
Nodes (7): audit(), _canonical(), _digest(), _equal(), main(), Independent row-level recomputation for the deterministic persona report., PersonaIndependentAuditTests

### Community 144 - "Code Community 144"
Cohesion: 0.28
Nodes (10): _association(), audit(), _canonical(), _digest(), main(), _pearson(), _ranks(), _rates() (+2 more)

### Community 145 - "Code Community 145"
Cohesion: 0.21
Nodes (8): _answer(), main(), Path, Zero-token active replay of mechanical smart-tool routes on historical HLE rows., _read(), score_predictions(), _write(), SmartToolHLEReplayTests

### Community 146 - "Code Community 146"
Cohesion: 0.15
Nodes (3): ModelLayerTests, Any LLM, through configuration rather than code., Only a live probe may return READY.

### Community 147 - "Code Community 147"
Cohesion: 0.18
Nodes (3): BehavioralRecordTests, Contract tests for the offline P0 profile-routing reproducibility layer., RoutingProxyTests

### Community 148 - "Code Community 148"
Cohesion: 0.31
Nodes (7): _check(), _digest(), _host(), _load_harness(), Regression tests for evidence-gated no-tools RPS interjection., _rival(), RPSInterjectionCalibrationTests

### Community 149 - "Code Community 149"
Cohesion: 0.21
Nodes (3): ManifestTests, SealedConditionMapTests, synthetic_items()

### Community 150 - "Code Community 150"
Cohesion: 0.29
Nodes (11): _key(), _merge_seen(), _norm_doi(), _norm_title(), Any, Path, Stateful Research Discovery runtime with scoped retrieval and source…, run_plan() (+3 more)

### Community 151 - "Code Community 151"
Cohesion: 0.24
Nodes (11): _digest(), main(), Path, verify(), load_rows(), main(), _parser(), ArgumentParser (+3 more)

### Community 152 - "Code Community 152"
Cohesion: 0.33
Nodes (11): antidiagonal_transpose(), apply_command(), flip(), main(), parse_question(), Independent post-score audit for the exact HLE array item used by hard-two.…, roll(), rotate() (+3 more)

### Community 155 - "Code Community 155"
Cohesion: 0.17
Nodes (6): EvidenceEstimatorTests, A classifier that never decides is never wrong; the calculator must not reward…, With the module's own defaults no admissible k exists. The honest answer is `k:…, D1, D2 - the classifier., P(theta > theta_hi) rises with every correct observation and falls with every…, The sufficiency gate must not be decided by sub-microsecond timing. Fresh…

### Community 156 - "Code Community 156"
Cohesion: 0.17
Nodes (5): obs(), Legacy rows predate timestamping; treating them as stale would void them., No correct observation can create or preserve a gap verdict where the verdict…, v1 returned UNCERTAIN for 20 correct and 1 incorrect., D2: the v1 two-observation gate is closed.

### Community 157 - "Code Community 157"
Cohesion: 0.23
Nodes (7): MigrationReceiptTests, Ledger audit section B — the measured defects, each named by the item it…, A v1 profile with one mechanically scored row and one ordinary-usage row., B1 — a migration that leaves no receipt cannot be audited later., `save()` refreshes `updated_at`; the receipt must still verify., Positive control: the digest is not a constant., v1_profile()

### Community 158 - "Code Community 158"
Cohesion: 0.17
Nodes (3): GuardBindingTests, B6 — a configuration that is not recorded cannot be attributed., Positive control: the guard refuses reuse, not every second run.

### Community 160 - "Code Community 160"
Cohesion: 0.21
Nodes (5): install_fake_claude(), PromptContractTests, Path, The matched-cost claim lives or dies here., Put an executable named `claude` in `directory` and return that directory.

### Community 162 - "Code Community 162"
Cohesion: 0.39
Nodes (11): _active_task(), build_state(), check(), diff_state(), _emit(), file_hash(), git_head(), main() (+3 more)

### Community 163 - "Code Community 163"
Cohesion: 0.36
Nodes (10): command_kind(), command_text(), dump(), load(), main(), Any, Path, sanitize_tool() (+2 more)

### Community 164 - "Code Community 164"
Cohesion: 0.27
Nodes (10): _assert_equal(), _canonical_digest(), _counts(), _file_sha256(), main(), _parser(), ArgumentParser, Path (+2 more)

### Community 165 - "Code Community 165"
Cohesion: 0.38
Nodes (10): _association(), audit(), _canonical(), _decision(), _digest(), main(), _pearson(), _ranks() (+2 more)

### Community 166 - "Code Community 166"
Cohesion: 0.36
Nodes (8): digest(), frozen_check(), host(), main(), rival(), run(), Structural-pilot tests for RPS v0.6.2., RPSV062StructuralPilotTests

### Community 167 - "Code Community 167"
Cohesion: 0.44
Nodes (10): calibration(), d(), ev_model(), formalization_policy(), instance_checks(), main(), route_binding(), _row() (+2 more)

### Community 169 - "Code Community 169"
Cohesion: 0.18
Nodes (3): PayloadHardeningTests, B3 — the profile file is attacker-reachable; the payload must not be., Positive control: the mark means something.

### Community 171 - "Code Community 171"
Cohesion: 0.25
Nodes (6): PrivateLeakTests, Positive control for the two path patterns added for D1. A pattern that never…, Every literal `appdata` in the tree, enumerated rather than assumed. The path…, (relative path, text) for every tracked text file outside the suite. Scoped to…, scanned_text_files(), tracked_paths()

### Community 172 - "Code Community 172"
Cohesion: 0.29
Nodes (8): _beta_quantile(), _bound_ppm(), _count(), jeffreys_bound_ppm(), _ppm(), Conservative pre-launch value gate for one bounded FOIL tool call.…, Return a closed, integer Jeffreys-Beta quantile for shared calibrators., Invert the regularized incomplete beta by bounded bisection.

### Community 173 - "Code Community 173"
Cohesion: 0.38
Nodes (9): _answer(), build_report(), _canonical(), _correct(), main(), Path, Replay frozen ProcessBench A0 outputs through the active RPS v0.6.3 gate. The…, _read_json() (+1 more)

### Community 174 - "Code Community 174"
Cohesion: 0.27
Nodes (5): Exception, E1 - the CLI reports a refusal, it does not crash with one. `NotCommitted`…, Negative control: only the gate's own refusal is formatted., Positive control: the wrapper is not what produces the exit code., ScoreRefusalPresentationTests

### Community 176 - "Code Community 176"
Cohesion: 0.29
Nodes (4): MalformedPayloadTests, B2 - an unreadable payload inside a frozen run fails closed. The hook cannot…, Same inputs, one variable different: FOIL_TASK_RUN is unset., Without this, the deny above could just be "the hook always denies".

### Community 177 - "Code Community 177"
Cohesion: 0.20
Nodes (4): Gold stays shut until the predictions cannot move without a trace., The positive control for the second condition. With `git status` stubbed clean,…, `cmd_score` must fail at the gate, not after touching the dataset., ScoreGateTests

### Community 179 - "Code Community 179"
Cohesion: 0.38
Nodes (3): _require_instance(), _require_sha256(), _require_text()

### Community 180 - "Code Community 180"
Cohesion: 0.36
Nodes (9): check(), main(), Any, Path, Evidence-ledger gate with backward-compatible content-addressed receipt…, Return (path, expected_sha256, error)., _receipt_integrity(), _resolve_evidence() (+1 more)

### Community 182 - "Code Community 182"
Cohesion: 0.36
Nodes (8): canonical_json(), independent_summary(), load_wrapper(), main(), Any, Path, Independent read-only audit for the sealed RPS v0.6.1 small shadow result., sha256_file()

### Community 183 - "Code Community 183"
Cohesion: 0.42
Nodes (8): decrypt(), derive_key(), fetch(), main(), normalize(), prepare(), row_fingerprint(), score()

### Community 185 - "Code Community 185"
Cohesion: 0.22
Nodes (3): The SPRT is a diagnostic second opinion, never the routed classifier., Two verified passes satisfy no evidence gate, yet the SPRT alone would already…, SprtCrossCheckTests

### Community 186 - "Code Community 186"
Cohesion: 0.36
Nodes (3): _digest(), R17ProtocolTests, _records()

### Community 187 - "Code Community 187"
Cohesion: 0.22
Nodes (4): DiscordanceAndReportTests, point_method_p(), Checks for `benchmarks/harness/paired_stats.py` against hand computation. Every…, The other standard two-sided exact construction, for cross-checking. "Sum the…

### Community 188 - "Code Community 188"
Cohesion: 0.44
Nodes (8): load_config(), _merge(), project_root(), Any, Path, PathLike, Shared configuration/runtime paths for the public Process Assurance tools., state_dir()

### Community 189 - "Code Community 189"
Cohesion: 0.46
Nodes (7): decrypt(), derive_key(), fetch(), main(), normalize(), prepare(), score()

### Community 190 - "Code Community 190"
Cohesion: 0.39
Nodes (7): _canonical_json(), _digest(), _file_sha256(), main(), Any, Independent arithmetic/conservation audit for the frozen small pilot., verify()

### Community 191 - "Code Community 191"
Cohesion: 0.39
Nodes (7): build_report(), _file_sha256(), main(), _observed(), Any, Deterministic synthetic integration pilot for the arithmetic rule bank., _request()

### Community 192 - "Code Community 192"
Cohesion: 0.39
Nodes (6): configure(), main(), prepare(), Any, Schema-fixed sealed wrapper for the RPS v0.6.1 small shadow benchmark. The…, schema_fixed()

### Community 193 - "Code Community 193"
Cohesion: 0.50
Nodes (7): fetch(), main(), normalize(), prepare(), score(), select_arc(), select_hle()

### Community 196 - "Code Community 196"
Cohesion: 0.25
Nodes (4): GapVocabularyDriftTests, B4 — the documented gap list and the list `add_gap` accepts must agree., Positive control: the vocabulary is enforced at write time., Any GAP_KINDS-shaped label in the skill text must be one the runtime takes.…

### Community 197 - "Code Community 197"
Cohesion: 0.36
Nodes (3): HookPayloadTests, B3 — the hook is what actually reaches the session., Positive control: silence means failure, not that the hook prints nothing.

### Community 200 - "Code Community 200"
Cohesion: 0.25
Nodes (4): B4 - the exact-name table matched case-sensitively, the patterns did not.…, Negative control: unrelated names still classify as unbudgeted., The unit test above is in-process; this is the host's contract., ToolNameNormalisationTests

### Community 201 - "Code Community 201"
Cohesion: 0.29
Nodes (5): Determinism, ProviderStatus, Enum, str, A benchmark cell needs replicates unless the model is genuinely seeded.

### Community 202 - "Code Community 202"
Cohesion: 0.25
Nodes (8): _claim_isolation_session(), claimed_isolation_sessions(), Sidecar index that records which isolation sessions a state file claimed., Every isolation session id already claimed anywhere in `state_dir`. The index…, Record the claim, or refuse it. Fails closed on a duplicate., Open a frozen run. `model`, `effort`, `allowed_tools` and…, session_index_path(), start_state()

### Community 203 - "Code Community 203"
Cohesion: 0.52
Nodes (6): fetch(), load_diamond(), main(), norm(), prepare(), score()

### Community 206 - "Code Community 206"
Cohesion: 0.48
Nodes (4): ActiveReplayTests, item(), Tests for the frozen-output active RPS replay., row()

### Community 207 - "Code Community 207"
Cohesion: 0.53
Nodes (4): d(), manifest(), ManifestContractTests, record()

### Community 209 - "Code Community 209"
Cohesion: 0.33
Nodes (3): LockReleaseTests, D6, D7 - the frozen-evaluation task/budget ledger. The guard is an accounting…, A killed holder must not leave the run permanently unusable.

### Community 214 - "Code Community 214"
Cohesion: 0.40
Nodes (4): _digest(), DiscoveryRequestError, The closed no-oracle request boundary was crossed., _request()

### Community 215 - "Code Community 215"
Cohesion: 0.53
Nodes (5): command(), ledger_gate(), main(), payload(), Claude Code hook adapter for deterministic Process Assurance gates.

### Community 216 - "Code Community 216"
Cohesion: 0.40
Nodes (3): MonitorAbsenceTests, FIX (gauntlet.monitor_structured): an empty trace is not-applicable, not a…, GUARD: a genuine violation still reports ISSUE, not UNKNOWN.

### Community 220 - "Code Community 220"
Cohesion: 0.40
Nodes (5): BudgetExhausted, LockTimeout, RuntimeError, Raised instead of allowing a governed operation to exceed its budget., Raised when the evaluation state lock could not be acquired in time.

### Community 221 - "Code Community 221"
Cohesion: 0.50
Nodes (3): main(), Small, keyless OpenAlex prior-art lookup used by Research Discovery., search_openalex()

## Knowledge Gaps
- **1 isolated node(s):** `RescueSpec`
  These have ≤1 connection - possible missing edges or undocumented components.
- **29 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `CompiledTaskSpec` connect `Code Community 8` to `Code Community 32`, `Code Community 65`, `Code Community 11`, `Code Community 39`?**
  _High betweenness centrality (0.001) - this node is a cross-community bridge._
- **Why does `Route` connect `Code Community 9` to `Code Community 7`, `Code Community 8`, `Code Community 11`, `Code Community 53`, `Code Community 30`?**
  _High betweenness centrality (0.000) - this node is a cross-community bridge._
- **Why does `SmartToolRuntimePolicy` connect `Code Community 2` to `Code Community 0`, `Code Community 9`, `Code Community 52`, `Code Community 87`, `Code Community 25`, `Code Community 60`?**
  _High betweenness centrality (0.000) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `RuntimeStore` (e.g. with `Receipt` and `RuntimeEvent`) actually correct?**
  _`RuntimeStore` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `RescueSpec` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Code Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.06317103620474407 - nodes in this community are weakly interconnected._
- **Should `Code Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.0680379746835443 - nodes in this community are weakly interconnected._