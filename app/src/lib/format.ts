/**
 * 展示层的格式化/换算工具（M6.3 起集中于此，避免同一算法在页面里各写一份）。
 *
 * 目前只有一处换算，但它是"口径"问题：写错不会报错，只会静默显示错数字，
 * 因此抽成纯函数并配测试。
 */

/**: 一棵树一年的碳吸收量（kg CO₂/年），用于"相当于种了多少棵树"的换算。 */
export const KG_CO2_PER_TREE_YEAR = 20;

/**
 * kg CO₂ → 等效树木棵数（年吸收量）。
 *
 * 注意 JS 运算符优先级：`x ?? 0 / 20` 解析为 `x ?? (0 / 20)`，
 * 除以 20 **从未生效** —— 这正是本函数要集中掉的那类错误。
 */
export function treesEquivalent(carbonReducedKg: number | null | undefined): number {
  const kg = carbonReducedKg ?? 0;
  return kg / KG_CO2_PER_TREE_YEAR;
}
