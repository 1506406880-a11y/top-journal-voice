# -*- coding: utf-8 -*-
"""指标元数据：每个指标的含义、优先级和改法。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class Metric:
    id: str
    label: str
    unit: str
    priority: int
    why: str
    fix_high: str
    fix_low: str = ""


METRICS: Dict[str, Metric] = {
    # 优先级 0：主张与证据的绑定，审稿人最先看
    "strong_claim_unsupported_per_k": Metric(
        "strong_claim_unsupported_per_k", "无支撑强断言", "次/千词", 0,
        "强断言（demonstrate / prove / establish / clearly）+ 无引文 + 无数据，是审稿意见里最常见的靶子。",
        "补证据，或把断言降级：demonstrate→show，prove→these results suggest，clearly→（删）。",
    ),
    "citation_end_ratio": Metric(
        "citation_end_ratio", "句末引文占比", "%", 0,
        "引文落在被支撑句的末尾，主张与证据同句；句首堆引文会切断这层关系。",
        "几乎每句都以引文收尾会读成文献清单；确认引文确实支撑该句，不要机械排布。",
        "把支撑引文移到被支撑句的句末；句首引文只用于承接前文，不用于支撑本句。",
    ),
    "booster_per_k": Metric(
        "booster_per_k", "强断言密度", "次/千词", 1,
        "顶刊正文的强断言远少于摘要式写作；密度高通常意味着结论强度超过证据。",
        "把 demonstrate / prove / establish 降级为 show / find / suggest；只有多组独立证据收敛时才用强断言。",
    ),
    "hedge_per_k": Metric(
        "hedge_per_k", "对冲词密度", "次/千词", 1,
        "对冲不是软弱，是把结论限定在证据覆盖的范围内。缺位会被读成过度解读。",
        "每一处限定都要有具体所指：样本、范围、模型假设。删掉空转的 possibly / potentially。",
        "检查是否把相关写成因果、把可能写成确定；讨论部分按证据强度补回限定。",
    ),
    "citation_per_k": Metric(
        "citation_per_k", "引文密度", "次/千词", 1,
        "引文密度本身不是目标，但没有来源的强主张一定是问题。",
        "引文过密会让段落变成文献清单；确认每处引文都在支撑具体主张。",
        "引文密度偏低时，检查每个强主张是否有来源；Nature 正文约 16–25 次/千词。",
    ),
    "citation_sentence_ratio": Metric(
        "citation_sentence_ratio", "带引文句占比", "%", 2,
        "用来判断引文是集中堆在少数句子里，还是均匀支撑论证。",
        "把堆在一句里的多条引文拆到各自支撑的主张上。",
    ),
    # 优先级 1：摘要与整体
    "abstract_words": Metric(
        "abstract_words", "摘要词数", "词", 1,
        "Nature 摘要中位约 210 词，通常四步：背景与缺口、做法、结果、意义。",
        "按四步压缩：一句缺口，一句做法，两三句结果，一句意义。删背景教科书式铺垫。",
        "摘要过短通常缺少结果或意义；补足关键数字与结论，不要补背景。",
    ),
    "abstract_sentence_mean": Metric(
        "abstract_sentence_mean", "摘要平均句长", "词", 2,
        "摘要句子比正文更短，读者要在三十秒内拿到结论。",
        "把摘要长句拆成主谓宾；一句只放一个结果。",
    ),
    "slop_per_k": Metric(
        "slop_per_k", "学术套词密度", "次/千词", 1,
        "delve / underscore / pivotal / realm 这类词在顶刊里不是禁用，但密度高时通常意味着句子没有具体对象。",
        "换成具体动作或对象：underscore→show，pivotal→（说清它决定了什么），robust→（说清对哪种扰动稳健）。",
    ),
    # 优先级 2：句子与段落
    "sentence_mean": Metric(
        "sentence_mean", "平均句长", "词", 2,
        "Nature 正文句长中位约 24 词。长句本身不是错，错的是一个句子里塞了多个主张。",
        "把插入语、条件从句独立成句；先让主谓出现。",
        "句子过碎会切断论证；合并同类项，不靠加连接词。",
    ),
    "long_sentence_ratio": Metric(
        "long_sentence_ratio", "超长句占比", "%", 2,
        "超过 35 词的句子，读者要回看主干。",
        "一句里超过两个从句就拆；把一个从句改成独立句或前置条件。",
    ),
    "paragraph_mean_words": Metric(
        "paragraph_mean_words", "段均词数", "词", 2,
        "一段只承担一个主张。段落过长通常意味着第二、第三个主张挤进来了。",
        "把第二个主张拆成新段；每段首句给出该段结论，后面给证据。",
        "段落过短会让论证碎片化；检查是否把同一主张切成了多段。",
    ),
    "nominalization_per_k": Metric(
        "nominalization_per_k", "名词化密度", "次/千词", 2,
        "implementation / assessment / utilization 把动作藏进名词，句子失去施动者。",
        "动词化：implementation→implement，assessment→assess，utilization→use。",
    ),
    "passive_per_k": Metric(
        "passive_per_k", "被动密度", "次/千词", 2,
        "Methods 允许被动；Results 与 Discussion 里被动会藏掉谁做了什么。",
        "Results/Discussion 优先主动，尤其是 we show / we find；Methods 保持现状。",
        "主动句偏多不算错；Methods 用被动是正常写法，确认没有把方法写成「我们做了」的口语叙述。",
    ),
    "first_person_per_k": Metric(
        "first_person_per_k", "第一人称密度", "次/千词", 2,
        "Nature 摘要与正文大量使用 we；把施动者全删掉不是客观，是含糊。",
        "补回 we / our，明确哪些工作是本研究的。",
        "we 过密会让每句都以作者开头；把方法细节交回被动。",
    ),
    "connective_per_k": Metric(
        "connective_per_k", "连接词密度", "次/千词", 2,
        "However / Therefore / Moreover 是路标，也是 AI 起草稿最常见的填充物。",
        "删掉句首连接词，让语序承担转折；真正需要显式路标时保留一处。",
    ),
    # 优先级 3：节奏与结构
    "sentence_cv": Metric(
        "sentence_cv", "句长变异系数", "CV", 3,
        "自然学术写作会有长短起伏；但不要为了 CV 机械造参差。",
        "检查是否每句同一骨架；改信息顺序，不要按字数硬拆。",
    ),
    "paragraph_cv": Metric(
        "paragraph_cv", "段长变异系数", "CV", 3,
        "段落长度全篇一致会让文章像卡片；但这不是硬指标。",
        "按论证需要分段，不按字数配额。",
    ),
    "title_words": Metric(
        "title_words", "题名词数", "词", 2,
        "顶刊题名短，主张明确，不用 'A study of' / 'Novel insights into' 这类壳。",
        "压到 15 词内：对象 + 动作 + 结果，删掉壳和形容词。",
    ),
    "section_count": Metric(
        "section_count", "节数", "节", 3,
        "结构本身不是语言问题，但缺 Results / Discussion 会直接影响可读性。",
        "按 Introduction / Results / Discussion / Methods 组织；方法放最后或补充材料。",
    ),
    # 中文档
    "sentence_mean_chars": Metric(
        "sentence_mean_chars", "平均句长", "字", 2,
        "中文 T1 期刊正文句长中位约 55 字，比通用写作长，因为论证需要限定与转折。",
        "把插入语和条件从句独立成句；一个句子只推进一步。",
        "句子过碎会切断论证；合并同一论点的分句。",
    ),
    "long80_ratio": Metric(
        "long80_ratio", "超长句占比", "%", 2,
        "超过 80 字的句子，读者要回看主干。",
        "在转折或举例处断开；不要让一个句子同时承担判断和证据。",
    ),
    "paragraph_mean_chars": Metric(
        "paragraph_mean_chars", "段均字数", "字", 2,
        "中文 T1 期刊段落中位约 260 字，一段一个论证单元。",
        "把第二个论点拆成新段；段首给判断，段中给材料，段末回扣。",
        "段落过短会让论证碎片化；合并同一论点的材料。",
    ),
    "metadiscourse_per_k": Metric(
        "metadiscourse_per_k", "元话语密度", "次/千字", 1,
        "「本文」「笔者」「值得注意的是」在 T1 期刊里密度很低；过密会让文章谈论自己而不是问题。",
        "删掉「本文认为」「值得注意的是」，直接给判断。",
    ),
    "abstract_chars": Metric(
        "abstract_chars", "摘要字数", "字", 1,
        "中文 T1 期刊摘要中位约 225 字，问题、方法、结果、价值四部分。",
        "压到四部分各一到两句；删背景铺陈。",
        "摘要过短通常缺结果或价值。",
    ),
    "title_chars": Metric(
        "title_chars", "题名字数", "字", 2,
        "中文期刊题名通常不超过 25 字，正副标题用冒号分隔。",
        "压到 25 字内：对象 + 判断，删「研究」「探析」「浅论」这类壳。",
    ),
}

PRIORITY_LABEL = {
    0: "P0 · 主张与证据",
    1: "P1 · 摘要与断言强度",
    2: "P2 · 句子与段落",
    3: "P3 · 节奏与结构",
}

PROFILE_ALIASES: Dict[str, str] = {
    "nature": "nature",
    "nature-en": "nature",
    "en": "nature",
    "cn": "cn-t1",
    "cn-t1": "cn-t1",
    "zh": "cn-t1",
}

CHECK_ORDER: Tuple[str, ...] = (
    "strong_claim_unsupported_per_k",
    "citation_end_ratio",
    "booster_per_k",
    "hedge_per_k",
    "citation_per_k",
    "citation_sentence_ratio",
    "slop_per_k",
    "abstract_words",
    "abstract_sentence_mean",
    "sentence_mean",
    "long_sentence_ratio",
    "paragraph_mean_words",
    "nominalization_per_k",
    "passive_per_k",
    "first_person_per_k",
    "connective_per_k",
    "sentence_cv",
    "paragraph_cv",
    "title_words",
    "sentence_mean_chars",
    "long80_ratio",
    "paragraph_mean_chars",
    "metadiscourse_per_k",
    "abstract_chars",
    "title_chars",
)
