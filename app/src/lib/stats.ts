/**
 * 极小统计工具：把"可能为空"的均值计算集中一处。
 *
 * 起因（评审 P1）：AIDecisionPage 直接写 `sum / aiCandidates.length`，
 * 候选列表为空时 `0 / 0 = NaN` 会显示到界面上。改为先经 `meanOf`：
 * **空集合一律返回 0，任何情况下都不产生 NaN/Infinity**。
 */

/** 算术平均；**忽略**非有限值；一个有限值都没有时返回 0（而不是 NaN）。 */
export function meanOf(values: readonly number[]): number {
  const finite = values.filter((v) => Number.isFinite(v))
  if (finite.length === 0) return 0
  const mean = finite.reduce((acc, v) => acc + v, 0) / finite.length
  return Number.isFinite(mean) ? mean : 0
}
