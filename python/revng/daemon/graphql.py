#
# This file is distributed under the MIT License. See LICENSE.md for details.
#

import asyncio
import json
import logging
from base64 import b64decode
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from typing import AsyncGenerator, Awaitable, Callable, Optional, ParamSpec, TypeVar

from starlette.datastructures import UploadFile

from ariadne import MutationType, QueryType, SubscriptionType, make_executable_schema
from ariadne import upload_scalar

from revng.api.manager import Manager
from revng.api.target import Target

from .event_manager import EventType, emit_event
from .multiqueue import MultiQueue
from .util import produce_serializer

executor = ThreadPoolExecutor(1)
invalidation_queue: MultiQueue[str] = MultiQueue()

T = TypeVar("T")
P = ParamSpec("P")


# Python runs all coroutines in the same event loop (which is handled by a single thread)
# The scheduling is done cooperatively, so once a coroutine starts executing it will run until
# the first call to `await` or `return`.
# This can work poorly if there are long-running sync function that are executed, since those block
# the event loop. To remedy this we use a separate thread to run these functions so that the event
# loop can run other coroutines in the meantime.
def run_in_executor(function: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> Awaitable[T]:
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(executor, partial(function, *args, **kwargs))


query = QueryType()
mutation = MutationType()
subscription = SubscriptionType()


@query.field("produce")
async def resolve_produce(
    obj, info, *, step: str, container: str, targetList: str, onlyIfReady=False  # noqa: N803
):
    manager: Manager = info.context["manager"]
    targets = targetList.split(",")
    result = await run_in_executor(manager.produce_target, step, targets, container, onlyIfReady)
    return produce_serializer(result)


@query.field("produceArtifacts")
async def resolve_produce_artifacts(
    obj, info, *, step: str, paths: Optional[str] = None, onlyIfReady=False  # noqa: N803
):
    manager: Manager = info.context["manager"]
    target_paths = paths.split(",") if paths is not None else None
    result = await run_in_executor(
        manager.produce_target, step, target_paths, only_if_ready=onlyIfReady
    )
    return produce_serializer(result)


@query.field("targets")
async def resolve_targets(_, info, *, step: str, container: str):
    manager: Manager = info.context["manager"]
    targets = await run_in_executor(manager.get_targets, step, container)
    return await run_in_executor(lambda: [t.as_dict() for t in targets])


@query.field("target")
async def resolve_target(_, info, *, step: str, container: str, target: str) -> Optional[Target]:
    manager: Manager = info.context["manager"]
    result = await run_in_executor(manager.deserialize_target, f"{step}/{container}/{target}")
    return result.as_dict() if result is not None else None


@query.field("getGlobal")
async def resolve_get_global(_, info, *, name: str) -> str:
    manager: Manager = info.context["manager"]
    return await run_in_executor(manager.get_global, name)


@query.field("verifyGlobal")
async def resolve_verify_global(_, info, *, name: str, content: str) -> bool:
    manager: Manager = info.context["manager"]
    result = await run_in_executor(manager.verify_global, name, content)
    return result.unwrap()


@query.field("verifyDiff")
async def resolve_verify_diff(_, info, *, globalName: str, content: str) -> bool:  # noqa: N803
    manager: Manager = info.context["manager"]
    result = await run_in_executor(manager.verify_diff, globalName, content)
    return result.unwrap()


@query.field("pipelineDescription")
async def resolve_pipeline_description(_, info) -> str:
    manager: Manager = info.context["manager"]
    return await run_in_executor(manager.get_pipeline_description)


@mutation.field("uploadB64")
@emit_event(EventType.BEGIN)
async def resolve_upload_b64(_, info, *, input: str, container: str):  # noqa: A002
    manager: Manager = info.context["manager"]
    await run_in_executor(manager.set_input, container, b64decode(input))
    await invalidation_queue.send("begin/input/:Binary")
    logging.info(f"Saved file for container {container}")
    return True


@mutation.field("uploadFile")
@emit_event(EventType.BEGIN)
async def resolve_upload_file(_, info, *, file: UploadFile, container: str):
    manager: Manager = info.context["manager"]
    contents = await file.read()
    await run_in_executor(manager.set_input, container, contents)
    await invalidation_queue.send("begin/input/:Binary")
    logging.info(f"Saved file for container {container}")
    return True


@mutation.field("runAnalysis")
@emit_event(EventType.CONTEXT)
async def resolve_run_analysis(
    _,
    info,
    *,
    step: str,
    analysis: str,
    containerToTargets: str | None = None,  # noqa: N803
    options: str | None = None,
):
    manager: Manager = info.context["manager"]
    target_map = json.loads(containerToTargets) if containerToTargets is not None else {}
    parse_options = json.loads(options) if options is not None else {}
    result = await run_in_executor(manager.run_analysis, step, analysis, target_map, parse_options)
    await invalidation_queue.send(str(result.invalidations))
    return json.dumps(result.result)


@mutation.field("runAnalysesList")
async def resolve_run_analyses_list(_, info, *, name: str, options: str | None = None):
    manager: Manager = info.context["manager"]
    parse_options = json.loads(options) if options is not None else {}
    result = await run_in_executor(manager.run_analyses_list, name, parse_options)
    await invalidation_queue.send(str(result.invalidations))
    return json.dumps(result.result)


@mutation.field("setGlobal")
@emit_event(EventType.CONTEXT)
async def mutation_set_global(_, info, *, name: str, content: str) -> bool:
    manager: Manager = info.context["manager"]
    result = await run_in_executor(manager.set_global, name, content)
    await invalidation_queue.send(str(result.invalidations))
    return result.result.unwrap()


@mutation.field("applyDiff")
@emit_event(EventType.CONTEXT)
async def mutation_apply_diff(_, info, *, globalName: str, content: str) -> bool:  # noqa: N803
    manager: Manager = info.context["manager"]
    result = await run_in_executor(manager.apply_diff, globalName, content)
    await invalidation_queue.send(str(result.invalidations))
    return result.result.unwrap()


@subscription.source("invalidations")
async def invalidations_generator(_, info) -> AsyncGenerator[str, None]:
    with invalidation_queue.stream() as stream:
        async for message in stream:
            yield message


@subscription.field("invalidations")
async def invalidations(message: str, info):
    return message


def get_schema():
    schema_file = (Path(__file__).parent.resolve()) / "schema.graphql"
    return make_executable_schema(
        schema_file.read_text(),
        query,
        mutation,
        subscription,
        upload_scalar,
    )