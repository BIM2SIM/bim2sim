"""Package holds aggregations. Those aggregate multiple elements to one element.
E.g. multiple thermal zones into one thermal zone
"""
import logging
from typing import Set, Sequence, TYPE_CHECKING
import inspect

if TYPE_CHECKING:
    from bim2sim.elements.base_elements import ProductBased

logger = logging.getLogger(__name__)


class AggregationMixin:
    guid_prefix = 'Agg'
    multi = ()
    aggregatable_classes: Set['ProductBased'] = set()

    def __init__(self, elements: Sequence['ProductBased'], *args, **kwargs):
        if self.aggregatable_classes:
            received = {type(ele) for ele in elements}
            mismatch = received - self.aggregatable_classes
            if mismatch:
                raise AssertionError("Can't aggregate %s from elements: %s" %
                                     (self.__class__.__name__, mismatch))
        # TODO: make guid reproduceable unique for same aggregation elements
        #  e.g. hash of all (ordered?) element guids?
        #  Needed for save/load decisions on aggregations
        self.elements = elements
        for model in self.elements:
            model.aggregation = self
        super().__init__(*args, **kwargs)

    @classmethod
    def __init_subclass__(cls, **kwargs):
        from bim2sim.elements.base_elements import ProductBased
        super().__init_subclass__(**kwargs)
        if "Mixin" not in cls.__name__:
            if ProductBased not in inspect.getmro(cls):
                logger.error("%s only supports sub classes of ProductBased", cls)

    def _calc_position(self, name):
        """Calculate the position based on first and last element."""
        if not self.elements:
            logger.debug(
                f"No elements found for {self.__class__.__name__}"
                f" ({self.guid})")
            return None
        try:
            first_pos = self.elements[0].position
            last_pos = self.elements[-1].position
            return (first_pos + last_pos) / 2
        except AttributeError:
            logger.warning(
                f"Elements missing 'position' attribute in"
                f" {self.__class__.__name__} ({self.guid})"
            )
            return None
        except Exception as ex:
            logger.warning(
                f"Position calculation failed for {self.__class__.__name__}"
                f" ({self.guid}): {ex}"
            )
            return None

    # def request(self, name):
    #     # broadcast request to all nested elements
    #     # if one attribute included in multi_calc is requested, all multi_calc attributes are needed
    #
    #     if name in self.multi:
    #         names = self.multi
    #     else:
    #         names = (name,)
    #
    #     # for ele in self.elements:
    #     #     for n in names:
    #     #         ele.request(n)
    #     decisions = DecisionBunch()
    #     for n in names:
    #         decisions.append(super().request(n))
    #     return decisions

    def source_info(self) -> str:
        return f'[{", ".join(e.source_info() for e in self.elements)}]'

    def __repr__(self):
        return "<%s (aggregation of %d elements)>" % (
            self.__class__.__name__, len(self.elements))

    def __str__(self):
        return "%s" % self.__class__.__name__
