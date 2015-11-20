import abc
from nala.structures.data import Entity
from nala import print_verbose, print_debug


class Evaluator:
    """
    Calculates precision, recall and subsequently F1 measure based on the original and the predicted mention
    to evaluate the performance of a model.

    Different implementations are possible based on the level of consideration such as:
        * Token level
        * Mention level
        * etc...
    """

    @abc.abstractmethod
    def evaluate(self, dataset):
        """
        :type dataset: nala.structures.data.Dataset
        :returns (precision, recall, f_measure): (float, float, float)
        """
        return


class MentionLevelEvaluator(Evaluator):
    """
    Implements mention level performance evaluation. That means it compares if the predicted text spans match
    the original annotated text spans.

    Whether a text spans matches and how we count that match is determined
    by the value of the parameter 'strictness'.
    """

    def __init__(self, strictness='exact', subclass_analysis=False):
        self.strictness = strictness
        """
        Determines whether a text spans matches and how we count that match, 3 possible values:
            * 'exact' count as:
                1 ONLY when we have exact match: (startA = startB and endA = endB)
            * 'overlapping' count as:
                1 when we have exact match
                1 when we have overlapping match
            * 'half_overlapping' count as:
                1 when we have exact match
                0.5 when we have overlapping match
        """
        self.subclass_analysis = subclass_analysis
        """
        Whether to report the performance for each subclass separately
        Can be used only with strictness='exact'
        """

    def evaluate(self, dataset):
        """
        :type dataset: nala.structures.data.Dataset
        :returns (tp, fp, fn, tp_overlapping, precision, recall, f_measure): (int, int, int, int, float, float, float)

        Calculates precision, recall and subsequently F1 measure, defined as:
            * precision: number of correctly predicted items as a percentage of the total number of predicted items
                len(predicted items that are also real)/len(predicted)
                or in other words tp / tp + fp
            * recall: number of correctly predicted items as a percentage of the total number of correct items
                len(real items that are also predicted)/len(real)
                or in other words tp / tp + fn
            * possibly considers overlapping matches as well

        Also prints the value of the calculated precision, recall, F1 measure
        as well as the value of the parameter 'strictness'.
        """
        tp, fp, fn, fp_overlap, fn_overlap = 0, 0, 0, 0, 0

        if self.subclass_analysis:
            # find all possible subclasses
            subclasses = set(ann.subclass for ann in dataset.annotations())
            subclasses.update(set(ann.subclass for ann in dataset.predicted_annotations()))
            # initialize counts to zero for each subclass
            subclass_counts = {subclass: dict.fromkeys(['tp', 'fp', 'fn', 'fp_overlap', 'fn_overlap'], 0)
                               for subclass in subclasses}

        for doc in dataset:
            for part in doc:
                print_debug(' || '.join(ann.text for ann in part.annotations))
                print_debug(' || '.join(ann.text for ann in part.predicted_annotations))
                print_debug()

                overlap_real = []
                overlap_predicted = []

                if self.subclass_analysis:
                    overlap_subclass_real = {subclass: [] for subclass in subclasses}
                    overlap_subclass_predicted = {subclass: [] for subclass in subclasses}

                Entity.equality_operator = 'exact'
                for ann in part.predicted_annotations:
                    if ann in part.annotations:
                        tp += 1
                        if self.subclass_analysis:
                            subclass_counts[ann.subclass]['tp'] += 1
                    else:
                        fp += 1
                        if self.subclass_analysis:
                            subclass_counts[ann.subclass]['fp'] += 1

                for ann in part.annotations:
                    if ann not in part.predicted_annotations:
                        fn += 1
                        if self.subclass_analysis:
                            subclass_counts[ann.subclass]['fn'] += 1

                Entity.equality_operator = 'overlapping'
                for ann_a in part.annotations:
                    for ann_b in part.predicted_annotations:
                        if ann_a == ann_b:
                            overlap_real.append(ann_a)
                            overlap_predicted.append(ann_b)

                            if self.subclass_analysis and ann_a.subclass == ann_b.subclass:
                                overlap_subclass_real[ann_a.subclass].append(ann_a)
                                overlap_subclass_predicted[ann_b.subclass].append(ann_b)

                Entity.equality_operator = 'exact'
                fp_overlap += sum(1 for ann in part.predicted_annotations if ann in overlap_predicted)
                fn_overlap += sum(1 for ann in part.annotations if ann in overlap_real)

                if self.subclass_analysis:
                    for subclass in subclasses:
                        subclass_counts[subclass]['fp_overlap'] += sum(1 for ann in part.predicted_annotations
                                                                       if ann in overlap_subclass_predicted[subclass]
                                                                       and ann.subclass == subclass)
                        subclass_counts[subclass]['fn_overlap'] += sum(1 for ann in part.annotations
                                                                       if ann in overlap_subclass_real[subclass]
                                                                       and ann.subclass == subclass)

        if self.subclass_analysis:
            for subclass, counts in subclass_counts.items():
                print('SUBCLASS {:4}'.format(subclass), end='\t')
                self.__calc_measures(counts['tp'], counts['fp'], counts['fn'], counts['fp_overlap'], counts['fn_overlap'])
            print('TOTAL'.ljust(14), end='\t')

        if self.subclass_analysis:
            return subclass_counts, self.__calc_measures(tp, fp, fn, fp_overlap, fn_overlap)
        else:
            return self.__calc_measures(tp, fp, fn, fp_overlap, fn_overlap)

    @staticmethod
    def __safe_division(nominator, denominator):
        try:
            return nominator / denominator
        except ZeroDivisionError:
            return float('NaN')

    def __calc_measures(self, tp, fp, fn, fp_overlap, fn_overlap):
        if self.strictness == 'exact':
            precision = self.__safe_division(tp, tp + fp)
            recall = self.__safe_division(tp, tp + fn)
        elif self.strictness == 'overlapping':
            fp = fp - fp_overlap
            fn = fn - fn_overlap

            precision = self.__safe_division(tp + fp_overlap + fn_overlap, tp + fp + fp_overlap + fn_overlap)
            recall = self.__safe_division(tp + fp_overlap + fn_overlap, tp + fn + fp_overlap + fn_overlap)
        elif self.strictness == 'half_overlapping':
            fp = fp - fp_overlap
            fn = fn - fn_overlap

            precision = self.__safe_division(tp + (fp_overlap + fn_overlap) / 2, tp + fp + fp_overlap + fn_overlap)
            recall = self.__safe_division(tp + (fp_overlap + fn_overlap) / 2, tp + fn + fp_overlap + fn_overlap)
        else:
            raise ValueError('strictness must be "exact" or "overlapping" or "half_overlapping"')

        f_measure = 2 * self.__safe_division(precision * recall, precision + recall)

        print_verbose('tp:{:4} fp:{:4} fn:{:4} fp_overlap:{:4} fn_overlap:{:4} '
                      .format(tp, fp, fn, fp_overlap, fn_overlap))

        print('p:{:.4f} r:{:.4f} f:{:.4f} strictness:{} '
              .format(precision, recall, f_measure, self.strictness))
        return tp, fp, fn, fp_overlap, fn_overlap, precision, recall, f_measure


class DocumentLevelRelationEvaluator(Evaluator):
    """
    Implements document level performance evaluation for relations. That means
    it extracts all unique relations from a document, and compares it with the
    predicted relations.

    The evaluator does not care about the order of entities in a relation and
    assumes that all relations are undirected.

    The comparision of unique relations can be done by the 'match_case'
    argument. If the value of 'match_case' is True, then a predicted relation
    will match only if the cases match. If set to False, both entities will be
    converted to lower case. By default, match_case is set to True.
    """
    def __init__(self, match_case=True):
        self.match_case = match_case
        """
        If set to True, two relations will match only if their entities have the
        same case. For instance, (entityA, entityB) and (EntityA, EntityB) will
        be considered different.

        However, if set to False, (entityA, entityB) is the same as
        (EntityA, EntityB).

        In general, (entityA, entityB) is also the same as (entityB, entityA)
        """

    def evaluate(self, dataset):
        """
        :type dataset: nala.structures.data.Dataset
        :returns (tp, fp, fn, precision, recall, f_measure): (int, int, int, float, float, float)

        Calculates precision, recall and subsequently F1 measure, defined as:
            * precision: number of correctly predicted items as a percentage of
                the total number of predicted items
                len(predicted items that are also real)/len(predicted)
                or in other words tp / tp + fp
            * recall: number of correctly predicted items as a percentage of
                the total number of correct items
                len(real items that are also predicted)/len(real)
                or in other words tp / tp + fn
            * f1 measure: the harmonic mean of precision and recall or in
                other words 2 * precision * recall / (precision + recall)

        Also prints the value of the calculated precision, recall, F1 measure
        as well as the value of the parameter 'match_case'.
        """

        tp, fp, fn = 0, 0, 0

        true_relations = {}
        for index, document in enumerate(dataset):
            relations = list(document.get_unique_relations())
            true_relations[index] = relations

        predicted_relations = {}
        for index, document in enumerate(dataset):
            relations = list(document.get_unique_predicted_relations())
            predicted_relations[index] = relations

        for key in true_relations.keys():
            predicted = predicted_relations[key]
            actual = true_relations[key]
            if self.match_case:
                predicted = [ x.lower() for x in predicted ]
                actual = [ x.lower() for x in actual ]
            for relation in predicted:
                if relation in actual:
                    tp += 1
                else:
                    fp += 1
            for relation in actual:
                if relation not in predicted:
                    fn += 1

        precision, recall, f_measure = self.__calc_measures(tp, fp, fn)
        return (tp, fp, fn, precision, recall, f_measure)

    @staticmethod
    def __safe_division(nominator, denominator):
        try:
            return nominator / denominator
        except ZeroDivisionError:
            return float('NaN')

    def __calc_measures(self, tp, fp, fn):
        precision = self.__safe_division(tp, tp+fp)
        recall = self.__safe_division(tp, tp+fn)
        f_measure = 2 * self.__safe_division(precision*recall, precision+recall)
        print_verbose('tp:{:4} fp:{:4} fn:{:4} '
                      .format(tp, fp, fn))
        print('p:{:.4f} r:{:.4f} f:{:.4f} match_case:{} '
              .format(precision, recall, f_measure, self.match_case))
        return (precision, recall, f_measure)