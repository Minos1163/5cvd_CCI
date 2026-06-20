# Lifecycle Fee Accounting V2 Review Advice

Date: 2026-06-19

Status: Research-only advice document

This document is written as a follow-up review of the V2 lifecycle fee accounting backtest report.
It does not approve live deployment.
It focuses on what V2 fixes correctly, what is still incomplete, and how to evolve the lifecycle research without drifting back into accounting ambiguity.

## Executive Conclusion

- V2 is a real improvement over V1 because partial exits are explicit, fees are audited on actual exited notional, the breakeven buffer is now modeled, and Probe disabled no longer downgrades into a misleading WATCH state.
- V2 is still not enough to approve live trading because the return target, win-rate target, and regime robustness target are all still below the stated goal.
- The right interpretation is not 'the strategy works'; it is 'the lifecycle accounting is now sane enough to support further research'.
- The correct next step is to keep V2 as the accounting baseline, then run a controlled research ladder across rolling windows, side-specific thresholds, and exit-side slippage modeling.

The main risk after V2 is not one obvious bug.
The main risk is subtle optimism creeping back in through the next layer of assumptions.

## What V2 Correctly Fixes

- Partial exits are now a first-class object rather than an implicit idea.
- Fees are no longer charged as if every partial exit were a full round trip.
- Breakeven includes a fee buffer, which reduces the chance of claiming false protection at the exact entry price.
- TP fractions were revised from 30/40/30 to 40/35/25, which is more realistic for early risk recovery and later trend participation.
- Max hold was shortened from 96 bars to 16 bars, which reduces stale capital lockup and forces the test to express edge sooner.
- Probe disabled now yields NO_TRADE with a clear PROBE_DISABLED reason, which is semantically cleaner than a WATCH downgrade.

These are not cosmetic changes.
They change the causal meaning of the backtest.
They also make future failure analysis much more credible.

## What V2 Still Does Not Prove

- V2 does not prove that the strategy is robust across multiple months of market regimes.
- V2 does not prove that the edge survives different volatility clusters.
- V2 does not prove that the current result is strong enough to satisfy the user's target of 50%+ 30D return and 80%+ win rate.
- V2 does not prove that exit-side slippage is fully modeled.
- V2 does not prove that long and short should share the same thresholds.
- V2 does not prove that symbol coverage is equally healthy across all included assets.
- V2 does not prove that the strategy is insensitive to small changes in hold cap or TP spacing.

In other words, V2 is a corrected measurement, not a final verdict.

## Interpret the Scoreboard Correctly

- The raw metric set is positive: +4.57% return, 68.70% win rate, PF 1.5472, Sharpe 1.7579, Sortino 3.1854, 115 trades.
- The raw metric set is also modest relative to the stated ambition.
- The result should be treated as a conservative baseline with positive expectancy, not as a deployable production edge.
- A good baseline is valuable because it gives the next iteration a trustworthy anchor.
- A misleadingly strong baseline is dangerous because it hides which refinements actually matter.

Therefore, the report should be read in two layers.
Layer one: the lifecycle accounting is now defensible.
Layer two: the market edge is still incomplete.

## Accounting Principles That Should Stay

- Fee accounting must remain tied to actual partial-exit notional.
- Exit metadata must preserve fraction, timestamp, price, reason, and bar offset.
- Breakeven logic must remain fee-aware and buffer-aware.
- Hold time must remain capped and recorded explicitly.
- Probe disabled behavior must remain a hard NO_TRADE rejection.
- All lifecycle state changes must remain serializable into the trade record.

These are structural requirements, not tuning knobs.

## Accounting Gaps That Still Need Work

- Exit-side slippage is still only partially modeled and should be added explicitly per partial exit.
- The reported costs still appear heavy relative to gross PnL, so cost sensitivity should be measured under multiple fee and slippage profiles.
- The report does not yet show MFE and MAE attribution, which is important for distinguishing good entries from good exits.
- The report does not yet isolate stop-hit timing distribution, which would help determine whether losses are mostly early noise or structural failure.
- The report does not yet quantify how much of the profit comes from TP ladder completion versus timeout exits versus breakeven stops.
- The report does not yet show whether costs are concentrated in one side, one symbol, or one bar regime.

These are the next accounting items to close.

## The Big Positive: The Thesis Survives the Fee Audit

- The most important result in V2 is not the return number itself.
- The most important result is that the lifecycle thesis remains positive after a more realistic cost model.
- That means the earlier edge was not entirely a fee illusion.
- That also means the lifecycle structure is worth continuing to research.
- The corrected fee model improves trust in the result even though it reduces the headline return.

That tradeoff is healthy.
A lower but more honest result is more useful than a higher but questionable one.

## Do Not Over-Interpret the Win Rate

- 68.70% win rate is strong, but it is not the same as robustness.
- Win rate can hide small average winners, concentrated winners, or regime dependence.
- A win-rate target of 80% should not be chased directly if it reduces expectancy or makes the strategy fragile.
- The real question is whether the PnL distribution remains stable when the market regime changes.
- The real question is whether the signal keeps its edge when costs rise or when momentum slows.

If the next iteration increases win rate by sacrificing trade quality, that is usually a bad trade.

## Do Not Over-Interpret the Profit Factor

- A profit factor of 1.5472 is healthy but not exceptional.
- It is good enough to justify further research.
- It is not good enough to ignore regime testing, symbol-level asymmetry, or tail risk.
- PF alone does not reveal whether the strategy depends on a narrow set of winners.
- PF alone does not reveal whether the strategy is vulnerable to one adverse month.

Use PF as a screening metric, not as a deployment passport.

## The Most Important Diagnostic Question

- Which component is actually creating the edge: entry quality, lifecycle management, or exit discipline?
- V2 improves lifecycle accounting, so the answer is still partially entangled.
- The next research task should separate entry edge from management edge.
- That can be done by holding the entry logic fixed while varying hold caps, TP fractions, and breakeven activation rules.
- It can also be done by testing long-only and short-only separately.

The strategy should not be credited for lifecycle edge if the entry edge is weak.

## Recommended Interpretation of the Exit Distribution

- TP ladder completion winning 18 trades suggests the trend continuation path exists, but it is not dominant.
- Breakeven stop hit on 35 trades suggests the strategy often gets enough follow-through to de-risk, but not enough to fully extend.
- Max hold exits being profitable indicates the hold cap is not merely a cleanup mechanism; it is contributing real realized edge.
- Stop hits remain the main loss source, which implies the original entry still needs refinement or the stop geometry still needs work.

The exit distribution says the lifecycle is functional.
It does not yet say the entry is optimal.

## What the Short Hold Cap Is Teaching You

- The reduction from 96 bars to 16 bars is important because it changes what kind of edge survives.
- A shorter cap forces the strategy to express itself in the near-term continuation path.
- That makes the result more relevant to the actual trading intent.
- It also helps prevent capital from being trapped in stale, low-quality positions.
- The fact that profitability survived the shorter cap is encouraging.

The next experiment should compare 8, 16, and 32 bars while keeping the entry rules frozen.

## Side-Specific Advice: Longs and Shorts Should Not Share the Same Thresholds Blindly

- The current result already suggests that shorts are materially stronger than longs.
- That asymmetry is not a minor detail; it is a design signal.
- The strategy should probably maintain side-specific thresholds for entry score, confidence, and possibly ATR tolerance.
- Longs may need stricter confirmation or narrower universe selection.
- Shorts may tolerate a different trigger profile because the market structure in the sample clearly favors them.

Do not force symmetry just because the code is cleaner.
For live research, statistical asymmetry matters more than aesthetic symmetry.

## Symbol-Specific Advice: Keep the Universe, but Rank It

- The profitable symbols are broad enough to be credible, which is good.
- But not all included symbols should be given equal research weight.
- A ranking layer should classify symbols into core, secondary, and watch-only buckets.
- That ranking should be based on win rate, expectancy, trade count, fee drag, and hold-time efficiency.
- Symbols with persistent negative or near-zero contribution should be demoted instead of being treated as equally valid.

Avoid making one bad symbol poison the whole universe.
Avoid making one good symbol hide the fact that others are weak.

## ADA and XMR Need Separate Attention

- ADAUSDT and XMRUSDT remain small-sample drags in the report.
- Small sample size means they should not be over-weighted.
- But they should also not be ignored if they keep showing up as structural underperformers in future windows.
- These symbols deserve their own threshold profile or a temporary exclusion rule in the research phase.
- If they remain weak after rolling windows, they should be blacklisted or placed in a lower-confidence bucket.

Do not let weak symbols dilute the quality of the research distribution.

## The XRP Blacklist Decision Should Stay Conservative

- The report says the XRP blacklist remains justified for this research phase.
- That is a reasonable conservative choice if XRP keeps failing the entry or lifecycle profile.
- However, blacklists should be versioned and time-bounded.
- A symbol should not be permanently blacklisted without periodic re-evaluation.
- Treat the blacklist as a research control, not as a moral judgment on the asset.

Use a periodic review rule so that the universe can recover if the symbol behavior changes.

## Fee Drag Is the Main Economic Constraint

- The cost / gross PnL ratio of 44.74% is large enough to matter materially.
- This means the strategy does not have a wide margin of safety.
- The next research stage should not only optimize gross PnL; it should explicitly optimize cost efficiency.
- A strategy that can survive fees is better than a strategy that merely outruns them in one window.
- The goal is to reduce cost leakage without overfitting the execution model.

Every 1 bp saved in realistic cost can matter more than a small theoretical signal tweak.

## Exit-Side Slippage Must Be Added

- The report already states that current slippage still only captures entry slippage.
- That is the first obvious next fix.
- Exit-side slippage should be modeled for each partial exit because TP fills and stop fills have different microstructure characteristics.
- Breakeven stops may have very different slippage behavior from profit-take exits.
- If exit-side slippage is ignored, the lifecycle thesis may still be slightly optimistic.

Model it explicitly rather than assuming symmetry.

## Partial Exits Need Richer Attribution

- Each partial exit should carry more than just price and fraction.
- It should ideally also carry the signal snapshot and local regime snapshot at exit time.
- This allows you to answer whether TP1, TP2, or TP3 is dominating in a particular regime.
- It also allows you to compare early exits versus late exits under different volatility conditions.
- That attribution is especially important if future tuning changes TP fractions again.

Without attribution, partial exits become accounting records rather than learning records.

## Breakeven Buffer Should Be Treated as a Tunable Safety Margin

- The 0.1% breakeven buffer is a sensible improvement.
- It protects the strategy from fee and tiny-slippage illusion around the entry price.
- That said, the optimal buffer may differ by symbol class, volatility regime, and side.
- A static buffer is acceptable as a baseline, but it should be tested at several values.
- Try at least 0.05%, 0.10%, and 0.15% in controlled experiments.

The buffer should not become a hidden source of survivorship bias.

## Max Hold Should Be Studied as a Parameter, Not Assumed

- The 16-bar cap is reasonable and may be closer to the true edge footprint.
- But it should be compared against 8 and 32 bars with all other parameters frozen.
- If 16 is best, the result is stronger because it is empirically supported.
- If 8 or 32 wins, the lifecycle needs to be reinterpreted.
- Do not treat 16 as final until the grid confirms it under rolling windows.

Hold cap should be an experiment, not a dogma.

## Probe Semantics Are Now Much Cleaner

- The switch from WATCH downgrade to hard NO_TRADE when Probe is disabled is correct.
- It removes ambiguity from the decision tree.
- It also makes logs and research statistics more honest, because the system no longer pretends a non-trade is a watchable setup.
- The new semantics are especially useful when building gating statistics or opportunity-funnel analysis.

Keep this behavior strict.
A disabled Probe should never silently become a softer state.

## Recommend Keeping Probe Disabled for Now

- The report's deployment decision to keep Probe disabled is prudent.
- Probe should remain disabled until it has its own positive-expectancy evidence.
- Probe can easily become a place where low-quality opportunities accumulate.
- That makes it a frequent source of hidden cost drag.
- If Probe is reintroduced too early, it may inflate activity without improving net expectancy.

Probe deserves a separate research track, not a default promotion.

## Rolling Windows Are Mandatory Before Any Deployment Discussion

- The single latest-30D window is not enough to validate robustness.
- At least 6 to 12 months of rolling 30D windows should be tested.
- That should include different trend regimes, crash regimes, and chop regimes.
- The rolling study should report median, interquartile range, and worst-window behavior.
- A strategy is much more believable when it survives the ugly windows as well as the good ones.

Use rolling windows to discover whether V2 is stable or merely lucky.

## Do Not Tune in Secret

- The report's next-work list is good because it names explicit experiments.
- That discipline should be preserved.
- Never silently change thresholds between runs and then compare the result as if nothing changed.
- Every parameter move should have an experiment ID and a hypothesis.
- If the next change improves one metric but hurts another, the tradeoff must be written down explicitly.

Hidden tuning is how research turns into self-deception.

## Recommended Experimental Ladder

- First fix accounting.
- Then fix exit-side slippage.
- Then compare hold caps 8 / 16 / 32.
- Then split long-only and short-only threshold profiles.
- Then test symbol buckets instead of a single uniform universe.
- Then run rolling windows.
- Only after that should any deployment gate be reconsidered.

This order matters.
If the order is changed, the interpretation becomes much weaker.

## What to Keep Frozen During the Next Research Window

- Keep the entry chain fixed while testing lifecycle parameters.
- Keep the universe fixed while testing side-specific thresholds.
- Keep fee assumptions fixed while testing hold and TP changes.
- Keep Probe disabled while evaluating the baseline lifecycle edge.
- Keep Binance client untouched unless a real bug is discovered in the execution adapter.

A clean experiment changes one family of variables at a time.

## What to Freeze Forever Unless Strong Evidence Says Otherwise

- Partial-exit audit fields should remain mandatory.
- TP ladders should always be fraction-aware.
- Breakeven should always include fees and a buffer.
- No-trade semantics should remain explicit when Probe is disabled.
- Trade records should always distinguish full exit, partial exit, and timeout exit.

These are design principles, not temporary patches.

## How to Read the Positive Expectancy Claim

- Positive expectancy in the theoretical check is encouraging, but it is not enough on its own.
- It is a consistency check, not a guarantee.
- Theoretical expectancy can still overestimate live-like performance if slippage, missed fills, or regime drift are under-modeled.
- Use it to rule out broken math, not to approve deployment.

If future theory checks become negative, stop and inspect the assumptions before running more backtests.

## How to Use the Profitability of Max-Hold Exits

- The fact that max-hold exits are profitable in the current window is useful.
- It suggests that some positions remain good enough even without fully reaching TP3.
- That means the hold cap is not merely a liability filter; it is also part of the edge capture mechanism.
- The next step is to see whether that profitability holds when the cap changes.

If max-hold profit collapses under a small cap change, the edge is more fragile than it looks.

## What the Stop-Hit Losses Are Telling You

- Stop hits remain the main loss source.
- That usually means one or more of the following is true:
- The entry is too early.
- The stop is too tight for the regime.
- The momentum confirmation is too weak.
- The symbol is too noisy.
- The side profile is mismatched.

Do not solve stop-hit losses by blindly widening stops.
Widening stops without adjusting size often just converts small losses into larger losses.

## Entry Quality Should Be Measured Separately From Lifecycle Quality

- The report currently validates lifecycle quality better than entry quality.
- That is fine, but it should be acknowledged explicitly.
- A strategy with good lifecycle handling can still have weak entries.
- Measure entry quality by holding the exit model fixed and comparing threshold profiles.
- If entry quality is weak, no amount of lifecycle polish will save the live system.

This distinction should remain central in the next report.

## A Good Future Report Should Answer These Questions

- Which symbols contribute most after fees?
- Which side contributes most after fees?
- Which exit reason contributes most after fees?
- Which hold cap is best under rolling windows?
- Which TP fraction profile is best under rolling windows?
- How much does exit-side slippage change the result?
- How sensitive is expectancy to fee assumptions?
- How sensitive is the strategy to changing Probe status?

A strong report answers all of these explicitly.

## Implementation Advice for the Next Codex Pass

- Keep the partial-exit dataclass or equivalent object as the primary lifecycle record.
- Keep fees calculated from the actual exited fraction, not the original full position size.
- Keep exit-side slippage as a separate line item.
- Keep breakeven activation rules side-aware and fee-aware.
- Keep configuration validation strict so the TP fractions always sum to 1.
- Keep report serialization deterministic and diffable.

These are engineering foundations, not optional polish.

## Suggested Acceptance Criteria for the Next Iteration

- Rolling 30D windows across at least 6 months show positive median expectancy.
- No single month catastrophically dominates the aggregate result.
- Long and short profiles are separately documented.
- Exit-side slippage is measured and reported.
- The result remains positive under at least one conservative slippage sensitivity test.
- The report explains why the strategy still misses the 50%+ / 80%+ target.

Passing these criteria would make the research materially stronger.

## What Not to Do Next

- Do not improve the report by hiding fee drag.
- Do not improve the report by removing hard losses from the summary.
- Do not improve the report by widening the experiment window until a good month is found.
- Do not re-enable Probe without a separate edge test.
- Do not claim live approval from a single positive 30D sample.

Any of those shortcuts would undo the value of V2.

## Practical Decision Summary

- Keep V2 as the corrected lifecycle baseline.
- Treat it as research evidence, not live authorization.
- Add exit-side slippage next.
- Run rolling windows next.
- Split long and short next.
- Test hold caps next.
- Re-evaluate the universe next.

The key is sequence, not enthusiasm.

## Bottom Line

- V2 is good enough to trust as a measurement baseline.
- V2 is not good enough to trust as a production edge.
- The accounting fixes were necessary and successful.
- The remaining gap is now a real market-edge question, not an accounting question.
- That is progress.

The next research stage should be designed to answer one thing only:
Does the positive expectancy survive realistic execution friction and time-regime variation?

## Appendix: Short Action List

- Add exit-side slippage per partial fill.
- Add MFE / MAE attribution.
- Add stop-hit timing attribution.
- Run 8 / 16 / 32 hold-cap comparisons.
- Run long-only and short-only profiles.
- Run rolling 30D windows across 6-12 months.
- Keep Probe disabled until it has a separate positive-expectancy test.
- Preserve the no-trade semantics for disabled Probe.

End of advice.

## Risk Questions to Answer Before Any Later Deployment Review

- What is the worst rolling 30D result?
- What is the median rolling 30D result?
- What is the interquartile range of returns?
- Which symbol has the worst fee-adjusted expectancy?
- Which side has the worst slippage-adjusted expectancy?
- How often does breakeven activate before timeout?
- How often does TP1 capture enough risk to protect the downside?
- How often does the stop hit before any meaningful follow-through?
- Does the profit factor remain above 1.2 under conservative cost stress?
- Does the strategy survive a 25% increase in slippage assumptions?

## Research Controls to Preserve

- Freeze the entry chain while testing lifecycle parameters.
- Freeze the universe while testing side-specific thresholds.
- Freeze the fee model while testing hold caps.
- Freeze the breakeven buffer while testing TP fractions.
- Record every experiment ID in the report header.
- Do not compare runs with different assumptions as if they were equivalent.
- Do not silently remove bad samples from the summary.
- Do not change the universe mid-window without versioning.
- Do not rename exit reasons between runs.
- Do not reuse a run ID after changing any economic assumption.

## Suggested Report Additions for V3

- Add a per-symbol fee drag chart.
- Add a per-side cost breakdown chart.
- Add a TP-hit sequence histogram.
- Add a stop-hit bar-offset distribution.
- Add an MAE-by-exit-reason table.
- Add an MFE-by-exit-reason table.
- Add a rolling expectancy curve.
- Add a monthly Sharpe heatmap.
- Add a cost sensitivity mini-table.
- Add a live-deployment gate checklist.

## Suggested Documentation Discipline

- Write one assumption per line.
- Write one result per line.
- Write one failure reason per line.
- Avoid mixing measurement and interpretation in the same sentence when possible.
- Use explicit labels for synthetic assumptions.
- Use explicit labels for fee-audited assumptions.
- Use explicit labels for conservative assumptions.
- Use explicit labels for any fixed universe or blacklist.
- Keep v1 and v2 files separate.
- Mark superseded conclusions clearly.

## Closing Recommendation Framework

- If a change increases expectancy but reduces sample size too much, keep it only if the rolling windows stay positive.
- If a change increases win rate but lowers PF materially, reject it unless it clearly improves stability.
- If a change reduces cost drag but worsens stop behavior, inspect the lifecycle distribution before accepting it.
- If a change improves one symbol while harming the universe average, prefer the universe average unless the symbol is explicitly reclassified.
- If a change makes the report harder to audit, reject it.

The research objective is not to make every metric move upward at once.
The objective is to make the lifecycle economics more truthful and more robust.

Keep the lifecycle record exact.
Keep the fee model explicit.
Keep the slippage model conservative.
Keep the breakeven rule fee-aware.
Keep the hold cap short enough to force freshness.
Keep the probe rejection semantic clear.
Keep the report versioned.
Keep the rollback path open.
Keep the conclusions research-only until rolling windows agree.
Keep the next experiment single-variable where possible.