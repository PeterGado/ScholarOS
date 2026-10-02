from dataclasses import dataclass

__all__ = ["SegmentTemplate", "SegmentTemplateEntry", "SEGMENT_TEMPLATES", "get_segment_template"]


@dataclass(frozen=True)
class SegmentTemplateEntry:
    """One row of a template - the same (name, instructions) shape WritingSegment itself takes,
    kept separate so a template entry can exist as plain reference data with no agent_id/
    segment_id, before it's ever applied to any real account.
    """

    name: str
    instructions: str


@dataclass(frozen=True)
class SegmentTemplate:
    """A named, predefined set of Writing Segments (2026-10-02) - built into the backend itself
    rather than tied to any one user's data, so it can be applied to any account on this
    instance, repeatedly, including after a workspace reset. Deliberately static/in-code for
    now (not a database-backed "save my own segments as a template" system) - the project owner
    asked for exactly one real guide to be built in; a general user-authored-template system is
    a bigger, different feature nobody has asked for yet, and would be easy to add later without
    disturbing this shape (ApplySegmentTemplateUseCase only depends on this dataclass, not on
    where instances of it come from).
    """

    template_id: str
    name: str
    description: str
    entries: tuple[SegmentTemplateEntry, ...]


FYP1_WRITING_GUIDE_TEMPLATE = SegmentTemplate(
    template_id="felc-unimas-fyp1",
    name="FELC UNIMAS - FYP1 Writing Guide",
    description=(
        "Chapter 1-3 structure for a UNIMAS Final Year Project Dissertation 1 (Introduction, "
        "Literature Review, Methodology), from the FELC FYP1 Writing Guide (prepared by Chuah "
        "Kee Man)."
    ),
    entries=(
        SegmentTemplateEntry(
            name="Ch1: Background of the Study",
            instructions=(
                "Start by explaining the current issues about the topic from a global/macro "
                "perspective (about 1-2 pages, cite 3-5 suitable studies). Then narrow down to "
                "the chosen context (e.g. a specific country) while still describing the "
                "general background, not the problem itself (about 1-2 pages, cite 3-5 "
                "suitable studies). Introduce the topic without yet addressing the detailed "
                "research problem."
            ),
        ),
        SegmentTemplateEntry(
            name="Ch1: Research Problem or Problem Statement",
            instructions=(
                "Begin by directly linking the background to the problem being studied. "
                "Justify the importance of addressing this problem using evidence from "
                "previous studies, citing specific details (avoid broad or vague statements). "
                "Clearly emphasise the gap in existing literature or the unresolved issue "
                "being explored - explain precisely what is not well understood. For action "
                "research, highlight how the study informs professional development as a "
                "teacher or impacts students. Write at least 2 pages. Do not mention the "
                "research method in this section."
            ),
        ),
        SegmentTemplateEntry(
            name="Ch1: Research Objectives or Research Questions",
            instructions=(
                "Start with a general aim in one sentence (e.g. 'This study aims to "
                "investigate the impact of artificial intelligence tools on students' ability "
                "to think critically'). Then list 3-4 research objectives or questions linked "
                "to the aim and the variables being studied. Make each objective or question "
                "measurable and focused."
            ),
        ),
        SegmentTemplateEntry(
            name="Ch1: Research Hypotheses (Optional)",
            instructions=(
                "Only needed if inferential statistics (e.g. t-test, ANOVA, Pearson's "
                "Correlation) will be used to address the research objectives/questions. "
                "Provide hypotheses preferably in Null Hypothesis format (Ho)."
            ),
        ),
        SegmentTemplateEntry(
            name="Ch1: Significance of the Study",
            instructions=(
                "Explain why the study is important both theoretically and practically (at "
                "least one point each). Theoretical: how the study addresses the identified "
                "gap in the literature or informs current theories/frameworks - include "
                "citations. Practical: discuss the potential impact on stakeholders or "
                "practical areas of use - include citations. Avoid general listing of "
                "significance without proper linkage to current situations or the scope of "
                "the study."
            ),
        ),
        SegmentTemplateEntry(
            name="Ch1: Operational Definition of Terms",
            instructions=(
                "Provide definitions of the keywords or variables in the topic, drawn from "
                "established research or books with citations (not a dictionary). Then "
                "operationalise each definition by explaining how the term is used in this "
                "study's context."
            ),
        ),
        SegmentTemplateEntry(
            name="Ch2: Theoretical Foundation",
            instructions=(
                "Start with a clear theoretical foundation - prefer specific frameworks or "
                "models over broad general theories (e.g. 'situated learning' or "
                "'scenario-based learning' rather than just 'constructivism'). Review 2-3 "
                "frameworks/models before indicating which one guides the study. Cite proper "
                "papers or books about the frameworks."
            ),
        ),
        SegmentTemplateEntry(
            name="Ch2: Review of Key Concepts",
            instructions=(
                "For each literature review heading, start by reviewing the underlying "
                "concepts or variables first (e.g. for 'Artificial Intelligence in "
                "Education', explain what AI is and how it relates to education before going "
                "further). Cite papers that clearly explain the concept. Keep these concepts "
                "related to the study's scope or objectives and keep the review neutral."
            ),
        ),
        SegmentTemplateEntry(
            name="Ch2: Review of Empirical Studies",
            instructions=(
                "After explaining the key concepts, provide evidence from empirical studies - "
                "papers with results and a clear mention of participants and methods. "
                "Describe studies one by one (one study per paragraph): the aim, target "
                "participants and location, method used, and key findings. Do not copy the "
                "study abstract - read the key parts and summarise. Organise studies from "
                "foreign contexts to local/closer contexts. Aim for about 4-5 empirical "
                "studies per heading/concept."
            ),
        ),
        SegmentTemplateEntry(
            name="Ch2: Review of Related Studies",
            instructions=(
                "Select at least 5 studies that are closely related to what is being "
                "investigated, to highlight the research gap further. Summarise each (aim, "
                "target participants and location, method, key findings) and explain the gap "
                "or weakness in each study. At the end of this section, restate the aim of "
                "this study and link it to the chosen theoretical framework."
            ),
        ),
        SegmentTemplateEntry(
            name="Ch2: Summary",
            instructions=(
                "Provide a chapter summary of the important details covered in the literature "
                "review - what was reviewed and the most important takeaways (typically the "
                "key gaps identified and the theoretical framework chosen)."
            ),
        ),
        SegmentTemplateEntry(
            name="Ch3: Research Design",
            instructions=(
                "Describe the overall approach (qualitative, quantitative, or mixed-methods). "
                "Justify why this design suits the research problem, citing at least 2 "
                "sources (research method books or journal papers using the same design). "
                "Mention how it aligns with the research objectives or questions."
            ),
        ),
        SegmentTemplateEntry(
            name="Ch3: Population and Sample (Participants)",
            instructions=(
                "Define the population being studied (a general number is sufficient). "
                "Explain the sampling technique (e.g. purposive, random, stratified) and why "
                "it suits the study. State the sample size and justify it (for a first "
                "dissertation stage, about 100 participants is typical for a purely "
                "survey-based study). Provide relevant sample details (e.g. target age)."
            ),
        ),
        SegmentTemplateEntry(
            name="Ch3: Research Setting",
            instructions=(
                "Describe where the research will take place (e.g. specific location, "
                "institution, or online environment) and explain why this setting is relevant "
                "or suitable."
            ),
        ),
        SegmentTemplateEntry(
            name="Ch3: Instrument",
            instructions=(
                "Provide details of the instrument to be used (e.g. questionnaire, interview, "
                "observation checklist, coding scheme). Clearly outline the items or "
                "questions and explain how they were developed (adapted, adopted, or "
                "self-constructed based on readings), with citations. A table comparing "
                "original and adapted items is beneficial. Briefly explain how reliability "
                "and validity will be ensured (e.g. Cronbach's alpha or pilot testing for "
                "quantitative; expert validation or source credibility for qualitative)."
            ),
        ),
        SegmentTemplateEntry(
            name="Ch3: Data Collection Procedure",
            instructions=(
                "Explain how data will be collected (e.g. survey, interviews, observation, "
                "document analysis) and justify why these methods are appropriate. Mention "
                "any instruments used (e.g. questionnaires)."
            ),
        ),
        SegmentTemplateEntry(
            name="Ch3: Data Analysis Methods",
            instructions=(
                "Explain how the data will be processed and analysed (e.g. thematic "
                "analysis, statistical tests, coding strategies) and justify why the chosen "
                "method fits the data type."
            ),
        ),
        SegmentTemplateEntry(
            name="Ch3: Ethical Considerations",
            instructions=(
                "Indicate how participants' rights will be protected (e.g. confidentiality, "
                "voluntary participation) and how collected data will be handled (e.g. "
                "retained for research purposes and deleted after a set period, such as 3 "
                "years)."
            ),
        ),
    ),
)

SEGMENT_TEMPLATES: tuple[SegmentTemplate, ...] = (FYP1_WRITING_GUIDE_TEMPLATE,)


def get_segment_template(template_id: str) -> SegmentTemplate | None:
    return next((t for t in SEGMENT_TEMPLATES if t.template_id == template_id), None)
