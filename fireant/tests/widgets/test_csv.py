from unittest import TestCase

import pandas as pd

from fireant import CSV
from fireant.tests.dataset.mocks import (
    CumSum,
    ElectionOverElection,
    dimx0_metricx1_df,
    dimx0_metricx2_df,
    dimx1_date_df,
    dimx1_date_operation_df,
    dimx1_num_df,
    dimx1_str_df,
    dimx2_date_num_df,
    dimx2_date_str_df,
    dimx2_date_str_ref_df,
    mock_dataset,
)
from fireant.utils import alias_selector as f


class CSVWidgetTests(TestCase):
    maxDiff = None

    def test_single_metric(self):
        result = CSV(mock_dataset.fields.votes) \
            .transform(dimx0_metricx1_df, mock_dataset, [], [])

        expected = dimx0_metricx1_df.copy()[[f('votes')]]
        expected.columns = ['Votes']

        self.assertEqual(expected.to_csv(), result)

    def test_multiple_metrics(self):
        result = CSV(mock_dataset.fields.votes, mock_dataset.fields.wins) \
            .transform(dimx0_metricx2_df, mock_dataset, [], [])

        expected = dimx0_metricx2_df.copy()[[f('votes'), f('wins')]]
        expected.columns = ['Votes', 'Wins']

        self.assertEqual(expected.to_csv(), result)

    def test_multiple_metrics_reversed(self):
        result = CSV(mock_dataset.fields.wins, mock_dataset.fields.votes) \
            .transform(dimx0_metricx2_df, mock_dataset, [], [])

        expected = dimx0_metricx2_df.copy()[[f('wins'), f('votes')]]
        expected.columns = ['Wins', 'Votes']

        self.assertEqual(expected.to_csv(), result)

    def test_time_series_dim(self):
        result = CSV(mock_dataset.fields.wins) \
            .transform(dimx1_date_df, mock_dataset, [mock_dataset.fields.timestamp], [])

        expected = dimx1_date_df.copy()[[f('wins')]]
        expected.index.names = ['Timestamp']
        expected.columns = ['Wins']

        self.assertEqual(expected.to_csv(), result)

    def test_time_series_dim_with_operation(self):
        query_dimensions = [mock_dataset.fields.timestamp]
        result = CSV(CumSum(mock_dataset.fields.votes)) \
            .transform(dimx1_date_operation_df, mock_dataset, query_dimensions, [])

        expected = dimx1_date_operation_df.copy()[[f('cumsum(votes)')]]
        expected.index.names = ['Timestamp']
        expected.columns = ['CumSum(Votes)']

        self.assertEqual(expected.to_csv(), result)

    def test_str_dim(self):
        result = CSV(mock_dataset.fields.wins) \
            .transform(dimx1_str_df, mock_dataset, [mock_dataset.fields.political_party], [])

        expected = dimx1_str_df.copy()[[f('wins')]]
        expected.index = pd.Index(['Democrat', 'Independent', 'Republican'], name='Party')
        expected.columns = ['Wins']

        self.assertEqual(expected.to_csv(), result)

    def test_int_dim(self):
        result = CSV(mock_dataset.fields.wins) \
            .transform(dimx1_num_df, mock_dataset, [mock_dataset.fields['candidate-id']], [])

        expected = dimx1_num_df.copy()[[f('wins')]]
        expected.index = pd.Index(list(range(1, 12)), name='Candidate ID')
        expected.columns = ['Wins']

        self.assertEqual(expected.to_csv(), result)

    def test_multi_dimx2_date_str(self):
        query_dimensions = [mock_dataset.fields.timestamp, mock_dataset.fields.political_party]
        result = CSV(mock_dataset.fields.wins) \
            .transform(dimx2_date_str_df, mock_dataset, query_dimensions, [])

        expected = dimx2_date_str_df.copy()[[f('wins')]]
        expected.index.names = ['Timestamp', 'Party']
        expected.columns = ['Wins']

        self.assertEqual(expected.to_csv(), result)

    def test_pivoted_single_dimension_transposes_data_frame(self):
        result = CSV(mock_dataset.fields.wins, pivot=[mock_dataset.fields.political_party]) \
            .transform(dimx1_str_df, mock_dataset, [mock_dataset.fields.political_party], [])

        expected = dimx1_str_df.copy()[[f('wins')]]
        expected.index = pd.Index(['Democrat', 'Independent', 'Republican'], name='Party')
        expected.columns = ['Wins']
        expected.columns.names = ['Metrics']
        expected = expected.transpose()

        self.assertEqual(expected.to_csv(), result)

    def test_pivoted_multi_dimx2_date_str(self):
        result = CSV(mock_dataset.fields.wins, pivot=[mock_dataset.fields.political_party]) \
            .transform(dimx2_date_str_df, mock_dataset,
                       [mock_dataset.fields.timestamp, mock_dataset.fields.political_party], [])

        expected = dimx2_date_str_df.copy()[[f('wins')]]
        expected = expected.unstack(level=[1])
        expected.index.names = ['Timestamp']
        expected.columns = ['Democrat', 'Independent', 'Republican']

        self.assertEqual(expected.to_csv(), result)

    def test_pivoted_multi_dimx2_date_num(self):
        query_dimensions = [mock_dataset.fields.timestamp, mock_dataset.fields['candidate-id']]
        result = CSV(mock_dataset.fields.votes, pivot=[mock_dataset.fields['candidate-id']]) \
            .transform(dimx2_date_num_df, mock_dataset, query_dimensions, [])

        expected = dimx2_date_num_df.copy()[[f('votes')]]
        expected = expected.unstack(level=1)
        expected.index.names = ['Timestamp']
        expected.columns = list(range(1, 12))

        self.assertEqual(expected.to_csv(), result)

    def test_time_series_ref(self):
        query_dimensions = [mock_dataset.fields.timestamp, mock_dataset.fields.political_party]
        query_references = [ElectionOverElection(mock_dataset.fields.timestamp)]
        result = CSV(mock_dataset.fields.votes) \
            .transform(dimx2_date_str_ref_df, mock_dataset, query_dimensions, query_references)

        expected = dimx2_date_str_ref_df.copy()[[f('votes'), f('votes_eoe')]]
        expected.index.names = ['Timestamp', 'Party']
        expected.columns = ['Votes', 'Votes EoE']

        self.assertEqual(expected.to_csv(), result)