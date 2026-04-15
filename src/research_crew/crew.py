"""The research crew — four agents, four tasks, sequential process."""

from __future__ import annotations

from crewai import Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task

from research_crew.logging_conf import get_logger
from research_crew.settings import settings
from research_crew.tools import build_web_search_tool

logger = get_logger(__name__)


@CrewBase
class ResearchCrew:
    """A multi-agent research crew that produces an executive brief.

    Flow:
        planner -> researcher -> analyst -> writer

    The crew is driven by YAML configuration files so that prompt changes
    can ship without touching Python.
    """

    agents: list[BaseAgent]
    tasks: list[Task]

    # Paths resolved relative to this module by @CrewBase.
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    # --- Agents ------------------------------------------------------------

    @agent
    def planner(self) -> Agent:
        return Agent(
            config=self.agents_config["planner"],  # type: ignore[index]
            llm=settings.model_name,
            verbose=True,
        )

    @agent
    def researcher(self) -> Agent:
        return Agent(
            config=self.agents_config["researcher"],  # type: ignore[index]
            llm=settings.model_name,
            tools=[build_web_search_tool()],
            verbose=True,
            max_iter=10,
        )

    @agent
    def analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["analyst"],  # type: ignore[index]
            llm=settings.model_name,
            verbose=True,
        )

    @agent
    def writer(self) -> Agent:
        return Agent(
            config=self.agents_config["writer"],  # type: ignore[index]
            llm=settings.model_name,
            verbose=True,
        )

    # --- Tasks -------------------------------------------------------------

    @task
    def plan_task(self) -> Task:
        return Task(config=self.tasks_config["plan_task"])  # type: ignore[index]

    @task
    def research_task(self) -> Task:
        return Task(config=self.tasks_config["research_task"])  # type: ignore[index]

    @task
    def analysis_task(self) -> Task:
        return Task(config=self.tasks_config["analysis_task"])  # type: ignore[index]

    @task
    def writing_task(self) -> Task:
        return Task(config=self.tasks_config["writing_task"])  # type: ignore[index]

    # --- Crew --------------------------------------------------------------

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
