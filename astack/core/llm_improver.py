"""
LLM-backed Factor Improver

使用 Claude (via AWS Bedrock) 读取因子代码 + 评估报告，
生成真正可执行的改进版 torch 因子代码。
"""

import json
import os
import re
import requests
from typing import Optional

from astack.schemas import AlphaSpec, ImprovementSpec, ValidationReport


# Bedrock 配置
DEFAULT_REGION = "us-east-1"
DEFAULT_MODEL = "us.anthropic.claude-sonnet-4-20250514-v1:0"

SYSTEM_PROMPT = """你是一个资深量化因子工程师，精通 PyTorch 和 alpha 因子开发。

你的任务是改进一个已有的量化因子。你会收到：
1. 因子的原始 Python 代码（使用 PyTorch tensor 操作）
2. 因子的回测评估报告（IC、分位数策略夏普、换手率等）
3. 改进方向建议

请生成改进版的因子函数代码。要求：
- 保持原因子的经济含义内核
- 使用与原代码相同的框架（PyTorch tensor, [N, T] 形状）
- 可用的辅助函数：rolling_mean, rolling_std, rolling_sum, lag, log_ret, _rolling_tsrank, _robust_norm_series, _signed_sqrt
- 函数签名必须是 def xxx(d: dict) -> torch.Tensor，其中 d 包含 'open', 'high', 'low', 'close', 'volume' 等 tensor
- 不引入新的外部依赖
- 不使用未来数据（所有 rolling/shift 只依赖当时及历史）
- 保持表达简洁

只输出 Python 代码，不需要解释。用 ```python 包裹。
"""


def _call_bedrock(prompt: str, system: str = SYSTEM_PROMPT) -> str:
    """调用 AWS Bedrock Claude API"""
    token = os.environ.get("AWS_BEARER_TOKEN_BEDROCK", "")
    if not token:
        raise RuntimeError("AWS_BEARER_TOKEN_BEDROCK not set")

    region = os.environ.get("AWS_REGION", DEFAULT_REGION)
    model = os.environ.get("ASTACK_LLM_MODEL", DEFAULT_MODEL)
    url = f"https://bedrock-runtime.{region}.amazonaws.com/model/{model}/invoke"

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    resp = requests.post(url, headers=headers, json=body, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"Bedrock API error {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    return data["content"][0]["text"]


def _extract_code(text: str) -> str:
    """从 LLM 输出中提取 Python 代码块"""
    match = re.search(r"```python\s*(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # fallback: 整段文本
    return text.strip()


class LLMFactorImprover:
    """使用 Claude 生成改进版因子代码"""

    def improve(
        self,
        spec: AlphaSpec,
        report: ValidationReport,
        source_code: str = "",
        improvement_hints: Optional[list] = None,
    ) -> ImprovementSpec:
        """生成改进版因子。

        Args:
            spec: 原因子定义
            report: 回测评估报告
            source_code: 原因子的 Python 源代码
            improvement_hints: 改进方向提示（如 ["降低换手", "正交化"]）
        """
        hints = improvement_hints or self._auto_hints(report)

        prompt = self._build_prompt(spec, report, source_code, hints)
        llm_output = _call_bedrock(prompt)
        improved_code = _extract_code(llm_output)

        improved_name = f"{spec.name}_llm_v2"
        new_spec = AlphaSpec(
            name=improved_name,
            description=f"{spec.description} [LLM improved: {'; '.join(hints)}]",
            formula_expression=improved_code[:200],
            required_fields=spec.required_fields,
            parameters=spec.parameters,
            direction=spec.direction,
            implementation_stub=improved_code,
        )

        return ImprovementSpec(
            original_name=spec.name,
            improved_name=improved_name,
            improvements=hints,
            new_spec=new_spec,
            expected_gains=f"LLM-generated improvement targeting: {', '.join(hints)}",
            risk_notes=["LLM 生成代码需要人工审查和回测验证"],
        )

    def _auto_hints(self, report: ValidationReport) -> list:
        """根据评估报告自动推导改进方向"""
        hints = []
        if report.turnover_risk == "high":
            hints.append("加入 EMA 平滑降低换手率")
        if report.redundancy_score > 0.5:
            hints.append("正交化处理降低与已有因子的相关性")
        if report.quality_score < 0.6:
            hints.append("除以 realized volatility 增强稳健性")
        # 检查分位数策略夏普
        sharpe = report.metrics.get("sharpe")
        if sharpe is not None and sharpe < 0:
            hints.append("改善信号形态使分位数突破策略夏普为正")
        if not hints:
            hints.append("微调信号结构提升预测力")
        return hints

    def _build_prompt(
        self, spec: AlphaSpec, report: ValidationReport,
        source_code: str, hints: list,
    ) -> str:
        metrics_str = json.dumps(report.metrics, indent=2, ensure_ascii=False)
        warnings_str = "\n".join(f"- {w}" for w in report.warnings) if report.warnings else "无"

        prompt = f"""请改进以下量化因子。

## 原因子信息
- 名称: {spec.name}
- 描述: {spec.description}
- 质量评分: {report.quality_score:.3f}
- 冗余度: {report.redundancy_score:.2f}
- 换手风险: {report.turnover_risk}

## 回测指标
{metrics_str}

## 警告
{warnings_str}

## 原因子代码
```python
{source_code if source_code else '(无源代码)'}
```

## 改进方向
{chr(10).join(f'- {h}' for h in hints)}

## 要求
1. 输出一个完整的改进版函数，签名为 def _{spec.name}_llm_v2(d: dict) -> torch.Tensor
2. 保持原因子的经济含义
3. 正交化系数要温和（0.05-0.15），避免过度正交化导致 IC 大幅下降
4. 平滑窗口 3-5 bar，不要太长
5. 波动率调整使用 rolling_std(log_ret(close), 20) 作为分母
6. 所有计算必须因果（无未来数据）
"""
        return prompt
