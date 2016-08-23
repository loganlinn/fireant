# coding: utf-8
from datetime import time

import numpy as np
import pandas as pd

from fireant.slicer.transformers import Transformer

NO_TIME = time(0)


def _format_data_point(value):
    if isinstance(value, str):
        return str(value)

    if isinstance(value, pd.Timestamp):
        if value.time() == NO_TIME:
            return value.strftime('%Y-%m-%d')
        else:
            return value.strftime('%Y-%m-%dT%H:%M:%S')

    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None

    if isinstance(value, np.int64):
        # Cannot transform np.int64 to json
        return int(value)

    return value


class DataTablesRowIndexTransformer(Transformer):
    def transform(self, dataframe, display_schema):
        has_references = isinstance(dataframe.columns, pd.MultiIndex)
        dataframe = self._prepare_dataframe(dataframe, display_schema['dimensions'])

        return {
            'columns': self._render_columns(dataframe, display_schema),
            'data': self._render_data(dataframe, display_schema),
        }

    def _prepare_dataframe(self, dataframe, dimensions):
        # Replaces invalid values and unstacks the data frame for column_index tables.
        return dataframe.replace([np.inf, -np.inf], np.nan)

    def _render_columns(self, dataframe, display_schema):
        dimensions = display_schema['dimensions']
        dimension_columns = [{'title': dimensions[dimension_key]['label'],
                              'data': '{}.display'.format(dimension_key)}
                             for dimension_key in dataframe.index.names
                             if dimension_key in dimensions]

        metric_columns = [self._render_column_level(metric_column, display_schema)
                          for metric_column in dataframe.columns]

        return dimension_columns + metric_columns

    def _render_column_level(self, metric_column, display_schema):
        if not isinstance(metric_column, tuple):
            return {'title': display_schema['metrics'][metric_column],
                    'data': metric_column}

        metric_key_idx = 1 if 'references' in display_schema else 0
        if metric_key_idx and metric_column[0]:
            reference_key = metric_column[0]
            metric_key = metric_column[1]
            data_keys = [reference_key, metric_key]
            metric_label = '{metric} {reference}'.format(
                metric=display_schema['metrics'][metric_key],
                reference=display_schema['references'][reference_key]
            )

        else:
            metric_key = metric_column[metric_key_idx]
            data_keys = [metric_key]
            metric_label = display_schema['metrics'][metric_key]

        return {
            'title': metric_label,
            'data': '.'.join(map(str, data_keys))
        }

    def _render_data(self, dataframe, display_schema):
        n = len(dataframe.index.levels) if isinstance(dataframe.index, pd.MultiIndex) else 1
        dimensions = list(display_schema['dimensions'].items())
        row_dimensions, column_dimensions = dimensions[:n], dimensions[n:]

        data = []
        for idx, df_row in dataframe.iterrows():
            row = {}

            if not isinstance(idx, tuple):
                idx = (idx,)

            for key, value in self._render_dimension_data(idx, row_dimensions):
                row[key] = value

            for key, value in self._render_metric_data(df_row, column_dimensions,
                                                       display_schema['metrics'], display_schema.get('references')):
                row[key] = value

            data.append(row)

        return data

    def _render_dimension_data(self, idx, dimensions):
        i = 0
        for key, dimension in dimensions:
            dimension_value = _format_data_point(idx[i])

            if 'label_field' in dimension:
                i += 1
                yield key, {'display': dimension_value,
                            'value': _format_data_point(idx[i])}

            elif 'label_options' in dimension:
                yield key, {'display': dimension['label_options'].get(dimension_value, dimension_value) or 'Total',
                            'value': dimension_value}

            else:
                yield key, {'display': dimension_value}

            i += 1

    def _render_metric_data(self, df, dimensions, metrics, references):
        if not isinstance(df.index, pd.MultiIndex):
            for metric_key, label in metrics.items():
                yield metric_key, _format_data_point(df[metric_key])

        if references:
            for reference in [''] + list(references):
                for key, value in self._recurse_dimensions(df[reference], dimensions, metrics, reference or None):
                    yield key, value
            return

        for key, value in self._recurse_dimensions(df, dimensions, metrics):
            yield key, value

    def _recurse_dimensions(self, df, dimensions, metrics, reference=None):
        if reference:
            return [(reference, dict(self._recurse_dimensions(df, dimensions, metrics)))]

        return [(metric_key, _format_data_point(df[metric_key]))
                for metric_key, label in metrics.items()]


class DataTablesColumnIndexTransformer(DataTablesRowIndexTransformer):
    def _prepare_dataframe(self, dataframe, dimensions):
        # Replaces invalid values and unstacks the data frame for column_index tables.
        dataframe = super(DataTablesColumnIndexTransformer, self)._prepare_dataframe(dataframe, dimensions)

        if 2 > len(dimensions):
            return dataframe

        unstack_levels = []
        for key, dimension in list(dimensions.items())[1:]:
            unstack_levels.append(key)
            if 'label_field' in dimension:
                unstack_levels.append(dimension['label_field'])

        return dataframe.unstack(level=unstack_levels)

    def _render_column_level(self, metric_column, display_schema):
        column = super(DataTablesColumnIndexTransformer, self)._render_column_level(metric_column, display_schema)

        # Iterate through the pivoted levels
        i = 2 if 'references' in display_schema else 1
        data_keys, levels = [], []
        for dimension_key, dimension in list(display_schema['dimensions'].items())[1:]:
            if 'label_options' in dimension:
                level_key = metric_column[i]
                level_label = (dimension['label_options'].get(level_key, None)
                               if not (isinstance(level_key, float) and np.isnan(level_key))
                               else 'Total')

            else:
                level_key = metric_column[i]

                if 'label_field' in dimension:
                    i += 1

                level_label = metric_column[i]

            # the metric key must remain last
            if not (isinstance(level_key, float) and np.isnan(level_key)):
                levels.append(level_label)
                data_keys.append(level_key)

            i += 1

        if levels:
            metric_label = '{metric} ({levels})'.format(
                metric=column['title'],
                levels=', '.join(levels)
            )
        else:
            metric_label = column['title']

        if data_keys and '.' in column['data']:
            # Squeeze the dimension levels between the reference and the metric
            data = column['data'].replace('.', '.' + ('.'.join(map(str, data_keys))) + '.')
        else:
            # Prepend the dimension levels to the metric
            data = '.'.join(map(str, data_keys + [column['data']]))

        return {
            'title': metric_label,
            'data': data
        }

    def _recurse_dimensions(self, df, dimensions, metrics, reference=None):
        if reference or not dimensions:
            return super(DataTablesColumnIndexTransformer, self)._recurse_dimensions(df, dimensions, metrics, reference)

        if 'label_field' in dimensions[0][1]:
            return [(key, dict(self._recurse_dimensions(df[:, key, display], dimensions[1:], metrics)))
                    for key, display in zip(*df.index.levels[1:3])]

        return [(level, dict(self._recurse_dimensions(df[:, level], dimensions[1:], metrics)))
                for level in df.index.levels[1]]


class CSVRowIndexTransformer(DataTablesRowIndexTransformer):
    def transform(self, dataframe, display_schema):
        csv_df = self._format_columns(dataframe, display_schema['metrics'], display_schema['dimensions'])

        if isinstance(dataframe.index, pd.RangeIndex):
            # If there are no dimensions, just serialize to csv without the index
            return csv_df.to_csv(index=False)

        csv_df = self._format_index(csv_df, display_schema['dimensions'])

        row_dimension_labels = self._row_dimension_labels(display_schema['dimensions'])
        return csv_df.to_csv(index_label=row_dimension_labels)

    def _format_index(self, csv_df, dimensions):
        levels = list(dimensions.items())[:None if isinstance(csv_df.index, pd.MultiIndex) else 1]

        csv_df.index = [self.get_level_values(csv_df, key, dimension)
                        for key, dimension in levels]
        csv_df.index.names = [key
                              for key, dimension in levels]
        return csv_df

    def get_level_values(self, csv_df, key, dimension):
        if 'label_options' in dimension:
            return [_format_data_point(dimension['label_options'].get(value, value))
                    for value in csv_df.index.get_level_values(key)]

        if 'label_field' in dimension:
            return [_format_data_point(data_point)
                    for data_point in csv_df.index.get_level_values(dimension['label_field'])]

        return [_format_data_point(data_point)
                for data_point in csv_df.index.get_level_values(key)]

    @staticmethod
    def _format_dimension_label(idx, dim_ordinal, dimension):
        if 'label_field' in dimension:
            label_field = dimension['label_field']
            return idx[dim_ordinal[label_field]]

        if isinstance(idx, tuple):
            id_field = dimension['id_fields'][0]
            dimension_label = idx[dim_ordinal[id_field]]

        else:
            dimension_label = idx

        if 'label_options' in dimension:
            dimension_label = dimension['label_options'].get(dimension_label, dimension_label)

        return dimension_label

    def _format_columns(self, dataframe, metrics, dimensions):
        return dataframe.rename(columns=lambda metric: metrics.get(metric, metric))

    def _row_dimension_labels(self, dimensions):
        return [dimension['label']
                for dimension in dimensions.values()]


class CSVColumnIndexTransformer(DataTablesColumnIndexTransformer, CSVRowIndexTransformer):
    def _format_columns(self, dataframe, metrics, dimensions):
        if 1 < len(dimensions):
            csv_df = self._prepare_dataframe(dataframe, dimensions)
            csv_df.columns = self._format_column_labels(csv_df, metrics, dimensions)
            return csv_df

        return super(CSVColumnIndexTransformer, self)._format_columns(dataframe, metrics, dimensions)

    def _row_dimension_labels(self, dimensions):
        return [dimension['label']
                for dimension in list(dimensions.values())[:1]]

    def _format_column_labels(self, csv_df, metrics, dimensions):
        column_labels = []
        for idx in list(csv_df.columns):
            metric_value, dimension_values = idx[0], idx[1:]

            dimension_labels = []
            for dimension_level, dimension_value in zip(csv_df.columns.names[1:], dimension_values):
                if 'label_options' in dimensions[dimension_level]:
                    dimension_label = dimensions[dimension_level]['label_options'].get(dimension_value, dimension_value)
                else:
                    dimension_label = dimension_value

                dimension_label = _format_data_point(dimension_label)

                if dimension_label is not None:
                    dimension_labels.append(dimension_label)

            if dimension_labels:
                column_labels.append('{metric} ({dimensions})'.format(
                    metric=metrics[metric_value],
                    dimensions=', '.join(dimension_labels),
                ))
            else:
                column_labels.append(metrics[metric_value])

        return column_labels
