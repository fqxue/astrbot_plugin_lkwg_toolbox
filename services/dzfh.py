import json
import re
from dataclasses import dataclass
from typing import Sequence

from playwright.async_api import Page

from .render import PageRenderService


MERCHANT_URL = "https://www.onebiji.com/hykb_tools/comm/lkwgmerchant/preview.php?id=1&immgj=0"
DZFH_URL = "https://www.onebiji.com/hykb_tools/lkwg/dzfh/index.php?immgj=1"


@dataclass(slots=True)
class DzfhService:
    renderer: PageRenderService

    async def render_merchant(self) -> str:
        async def prepare(page: Page) -> None:
            await page.wait_for_function(
                """
                () => [...document.querySelectorAll('.sp-time em')]
                    .some(el => /\\d{2}:\\d{2}:\\d{2}/.test(el.textContent || ''))
                """
            )

        return await self.renderer.screenshot_locator(
            page_url=MERCHANT_URL,
            locator="div.shop-box",
            name_prefix="merchant",
            viewport={"width": 1280, "height": 2000},
            prepare=prepare,
        )

    async def render_egggroup(self, keyword: str, *, only_shiny: bool = False) -> str:
        async def prepare(page: Page) -> None:
            await page.wait_for_function("() => window.ToolPage && window.$ && window.pageData")
            await page.evaluate(
                """
                ({ keyword, onlyShiny }) => {
                    document.querySelectorAll('.hd-nav a').forEach((el, index) => {
                        el.classList.toggle('on', index === 0);
                    });
                    document.querySelectorAll('.qu-con').forEach((el, index) => {
                        el.style.display = index === 0 ? 'block' : 'none';
                    });

                    const searchResult = ToolPage.getPokemonSearchResult(keyword);
                    const target = searchResult.find(item => item.name === keyword) || searchResult[0];
                    if (!target) {
                        throw new Error(`未找到精灵: ${keyword}`);
                    }

                    const pokemon = ToolPage.getPokemonInfo(target.id);
                    let html = '';
                    html += '<div class="ef-item">';
                    html += '    <div>';
                    html += `        <img class="pokemon-img" src="${pokemon.img}" alt="${pokemon.name}">`;
                    html += '    </div>';
                    html += `    <span><em><i>${pokemon.name}</i></em></span>`;
                    html += `    <p>${ToolPage.getPokemonGroupAttrHtml(pokemon.groups)}</p>`;
                    html += '</div>';

                    $('#search-keyword').val(keyword);
                    $('#egg-group-box').addClass('on');
                    $('#egg-group-result-box').html(html);
                    $('#egg-group-result').show();

                    $(".ef-item span").each(function () {
                        ToolPage.textToLong($(this));
                    });

                    ToolPage.searchGroupResult = {};
                    $.each(pokemon.groups, function (_, group) {
                        if (ToolPage.pokemonGroupList[group]) {
                            $.each(ToolPage.pokemonGroupList[group], function (_, poke) {
                                if (pokemon.id != poke.id) {
                                    ToolPage.searchGroupResult['_' + poke.id] = poke;
                                }
                            });
                        }
                    });

                    const shinyBtn = document.querySelector('#egg-group-only-ys-btn');
                    shinyBtn?.classList.toggle('on', !!onlyShiny);

                    const result = ToolPage.filterPokemonGroupResult();
                    ToolPage.renderPokemonGroupHtml(result, true);
                }
                """,
                {"keyword": keyword, "onlyShiny": only_shiny},
            )
            await page.locator("#egg-group-result").wait_for(state="visible")
            await self.renderer.hydrate_lazy_images(page, "#egg-group-box img.lazyload")
            await self.renderer.wait_images_ready(page, "#egg-group-box img")

        return await self.renderer.screenshot_locator(
            page_url=DZFH_URL,
            locator="#egg-group-box",
            name_prefix="egggroup",
            viewport={"width": 1280, "height": 2200},
            prepare=prepare,
        )

    async def render_hatch(self, size: str, weight: str) -> str:
        async def prepare(page: Page) -> None:
            await page.wait_for_function("() => window.$ && window.pageData && window.ToolPage")
            await page.evaluate(
                """
                ({ sizeValue, weightValue }) => {
                    const size = parseFloat(sizeValue);
                    const weight = parseFloat(weightValue);
                    const result = {
                        very_high: [],
                        high: [],
                        middle: [],
                        low: [],
                    };

                    const candidates = Object.values(pokemonList)
                        .filter((pokemon) => pokemon.size && pokemon.weight)
                        .map((pokemon) => {
                            const sizeDiff = Math.abs(parseFloat(pokemon.size) - size);
                            const weightDiff = Math.abs(parseFloat(pokemon.weight) - weight);
                            const score = sizeDiff / 0.02 + weightDiff / 1.5;
                            return { pokemon, score };
                        })
                        .sort((a, b) => a.score - b.score)
                        .slice(0, 20);

                    candidates.forEach(({ pokemon, score }) => {
                        if (score <= 0.5) {
                            result.very_high.push(pokemon);
                        } else if (score <= 1.5) {
                            result.high.push(pokemon);
                        } else if (score <= 3) {
                            result.middle.push(pokemon);
                        } else if (score <= 6) {
                            result.low.push(pokemon);
                        }
                    });

                    $('#egg-size').val(sizeValue);
                    $('#egg-weight').val(weightValue);
                    $('#egg-search-result-box').show();

                    if (ToolPage.hasHatchEggSearchResult(result)) {
                        $('#egg-search-result-empty').hide();
                        $('#egg-search-result').show().html(ToolPage.getHatchEggSearchResultHtml(result));
                    } else {
                        $('#egg-search-result').hide().empty();
                        $('#egg-search-result-empty').show();
                    }
                }
                """,
                {"sizeValue": size, "weightValue": weight},
            )
            await page.locator("#egg-search-result-box").wait_for(state="visible")
            await self.renderer.hydrate_lazy_images(page, "#egg-search-result-box img.lazyload")
            await self.renderer.wait_images_ready(page, "#egg-search-result-box img")

        return await self.renderer.screenshot_locator(
            page_url=DZFH_URL,
            locator="#egg-search-result-box",
            name_prefix="hatch",
            viewport={"width": 1280, "height": 2200},
            prepare=prepare,
        )

    async def render_planner_demo(self, target: str | None = None) -> tuple[str, str]:
        return await self.render_planner_route(target or "奇丽草", parents=None, sex="male", demo_mode=True)

    async def render_planner_route(
        self,
        target: str,
        *,
        parents: Sequence[str] | None,
        sex: str,
        demo_mode: bool = False,
    ) -> tuple[str, str]:
        async def prepare(page: Page) -> None:
            await page.wait_for_function("() => window.$ && window.pageData && window.ToolPage")
            chosen_name = await page.evaluate(
                """
                ({ targetKeyword, parentKeywords, sex }) => {
                    const normalize = (name) => {
                        const result = ToolPage.getPokemonSearchResult(name || '');
                        return result.find(item => item.name === name) || result[0] || null;
                    };

                    document.querySelectorAll('.hd-nav a').forEach((el, index) => {
                        el.classList.toggle('on', index === 2);
                    });
                    document.querySelectorAll('.qu-con').forEach((el, index) => {
                        el.style.display = index === 2 ? 'block' : 'none';
                    });

                    const targetPokemon = normalize(targetKeyword);
                    if (!targetPokemon) {
                        throw new Error(`未找到目标精灵: ${targetKeyword}`);
                    }

                    const chosenParents = (parentKeywords && parentKeywords.length ? parentKeywords : [targetPokemon.name])
                        .map(normalize)
                        .filter(Boolean);
                    if (!chosenParents.length) {
                        throw new Error('未找到可用父本');
                    }

                    ToolPage.plannerSelectedSex = sex || 'male';
                    ToolPage.plannerSelectedList = chosenParents.map((pokemon) => ({
                        id: pokemon.id,
                        sex: sex || 'male',
                    }));
                    ToolPage.renderPlannerSelectedList();

                    ToolPage.plannerTargetPokemonId = targetPokemon.id;
                    ToolPage.renderPlannerTargetResultItem();
                    ToolPage.plannerResultList = {};

                    let html = '';
                    chosenParents.forEach((pokemon) => {
                        ToolPage.plannerResultList[pokemon.id] = {
                            id: pokemon.id,
                            sex: sex || 'male',
                            data: {},
                            path_num: 1,
                            total_step: 1,
                            sort_num: 1,
                            path_length: 1,
                            msg: '本地演示路径'
                        };

                        html += `<div class="pt-box" data-parent-id="${pokemon.id}">`;
                        html += ToolPage.getPlannerResultHeaderHtml(pokemon.id, sex || 'male', true);
                        html += '<div class="planner-path-box">';
                        html += ToolPage.getPlannerFlowBoxHtml(pokemon.id, targetPokemon.id, pokemon.id, 1);
                        html += '</div>';
                        html += '</div>';
                    });

                    $('#planner-result-list').html(html);
                    $('#planner-result-box').show();

                    return targetPokemon.name;
                }
                """,
                {
                    "targetKeyword": target,
                    "parentKeywords": list(parents) if parents else [],
                    "sex": sex,
                },
            )
            await self.renderer.hydrate_lazy_images(page, "#planner-result-box img.lazyload, #planner-target-result-item img.lazyload, #planner-selected-list img.lazyload")
            await self.renderer.wait_images_ready(page, ".qu-con img")
            page._chosen_name = chosen_name  # type: ignore[attr-defined]

        path = await self.renderer.screenshot_locator(
            page_url=DZFH_URL,
            locator=".qu-con:nth-of-type(3)",
            name_prefix="planner",
            viewport={"width": 1280, "height": 2600},
            prepare=prepare,
        )
        label = "本地演示" if demo_mode else "本地参数预览"
        return path, label

    @staticmethod
    def normalize_parent_list(value: str | None) -> list[str]:
        if not value:
            return []
        return [item.strip() for item in re.split(r"[,，]", value) if item.strip()]
