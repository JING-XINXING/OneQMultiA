/** 把抓取层技术错误转成试用用户能看懂的说明。 */

const RULES: { test: RegExp; title: string; hint: string }[] = [
  {
    test: /未检测到回答|response_container|选择器不匹配/,
    title: "没有读到回答内容",
    hint: "页面可能已改版，或回答还在生成。可稍后重试，或到「平台」里检查该助手。",
  },
  {
    test: /找不到输入框|input_box|textarea/,
    title: "打不开提问框",
    hint: "多半尚未登录，或页面结构变化。请先在调试版 Chrome 打开该平台并登录。",
  },
  {
    test: /超时|timeout/i,
    title: "等待超时",
    hint: "该助手响应较慢或页面卡住，可单独重试，或先看其他已成功的回答。",
  },
  {
    test: /取消|已终止|cancelled/i,
    title: "已停止提问",
    hint: "本轮请求已手动终止。",
  },
  {
    test: /登录|login|未登录/,
    title: "需要登录",
    hint: "到「平台」打开该助手并完成登录后，再重新提问。",
  },
];

export function friendlyError(raw: string): { title: string; hint: string } {
  const text = (raw || "").trim();
  if (!text) return { title: "回答失败", hint: "可稍后重试，或换一批平台再问。" };
  const hit = RULES.find((rule) => rule.test.test(text));
  return hit ?? { title: "暂时无法完成回答", hint: text };
}
