#!/usr/bin/env python3
"""
Advanced Statistics Module for Netperf-Aggregate

Provides confidence intervals, outlier detection, hypothesis testing,
and distribution analysis for netperf results.

Author: Netperf Modernization Project - Phase 3
License: MIT
Version: 2.0.0
"""

import math
import random
import statistics
from typing import List, Dict, Any, Tuple, Optional


class AdvancedStatistics:
    """Advanced statistical analysis for netperf results"""
    
    @staticmethod
    def calculate_comprehensive_stats(values: List[float], 
                                     confidence_level: float = 0.95,
                                     detect_outliers: bool = True,
                                     outlier_method: str = 'iqr') -> Dict[str, Any]:
        """Calculate comprehensive statistics with CI, outliers, and distribution analysis
        
        Args:
            values: List of numeric values
            confidence_level: Confidence level for CI (default 0.95 for 95%)
            detect_outliers: Whether to detect and report outliers
            outlier_method: 'iqr' or 'zscore'
            
        Returns:
            Dictionary with comprehensive statistical measures
        """
        if not values:
            return {}
        
        n = len(values)
        values_sorted = sorted(values)
        
        # Basic statistics
        stats = {
            'count': n,
            'mean': statistics.mean(values),
            'median': statistics.median(values),
            'min': min(values),
            'max': max(values),
            'range': max(values) - min(values),
        }
        
        # Variance and standard deviation (requires n >= 2)
        if n >= 2:
            stats['stddev'] = statistics.stdev(values)
            stats['variance'] = statistics.variance(values)
            stats['coefficient_of_variation'] = (stats['stddev'] / stats['mean'] * 100) if stats['mean'] != 0 else 0
            stats['std_error'] = stats['stddev'] / math.sqrt(n)
        else:
            stats['stddev'] = 0
            stats['variance'] = 0
            stats['coefficient_of_variation'] = 0
            stats['std_error'] = 0
        
        # Percentiles
        stats['p50'] = values_sorted[int(n * 0.50)]
        stats['p90'] = values_sorted[int(n * 0.90)] if n > 1 else values_sorted[0]
        stats['p95'] = values_sorted[int(n * 0.95)] if n > 1 else values_sorted[0]
        stats['p99'] = values_sorted[int(n * 0.99)] if n > 1 else values_sorted[0]
        
        # Confidence intervals (requires n >= 2)
        if n >= 2:
            ci = AdvancedStatistics.confidence_interval(values, confidence_level)
            stats['ci_lower'] = ci[0]
            stats['ci_upper'] = ci[1]
            stats['ci_margin'] = (ci[1] - ci[0]) / 2
            stats['ci_level'] = confidence_level
            stats['ci_range'] = ci[1] - ci[0]
        
        # Outlier detection
        if detect_outliers and n >= 4:
            outlier_info = AdvancedStatistics.detect_outliers(values, method=outlier_method)
            stats['outliers'] = outlier_info['outliers']
            stats['outlier_count'] = len(outlier_info['outliers'])
            stats['outlier_indices'] = outlier_info['indices']
            stats['outlier_percentage'] = (len(outlier_info['outliers']) / n) * 100
            
            # Recalculate stats without outliers if any found
            if stats['outlier_count'] > 0 and len(outlier_info['clean_values']) >= 2:
                stats['mean_clean'] = statistics.mean(outlier_info['clean_values'])
                stats['median_clean'] = statistics.median(outlier_info['clean_values'])
                stats['stddev_clean'] = statistics.stdev(outlier_info['clean_values'])
                stats['improvement_pct'] = ((stats['mean_clean'] - stats['mean']) / stats['mean'] * 100) if stats['mean'] != 0 else 0
        
        # Distribution analysis (requires n >= 3)
        if n >= 3:
            dist_info = AdvancedStatistics.analyze_distribution(values)
            stats['skewness'] = dist_info['skewness']
            stats['kurtosis'] = dist_info['kurtosis']
            stats['skewness_interpretation'] = dist_info['interpretation']['skewness']
            stats['kurtosis_interpretation'] = dist_info['interpretation']['kurtosis']
            
            if n >= 8:  # More reliable with larger samples
                stats['is_normal'] = dist_info['is_normal']
                stats['normality_p_value'] = dist_info['p_value']
        
        return stats
    
    @staticmethod
    def confidence_interval(values: List[float], confidence: float = 0.95,
                           method: str = 'auto') -> Tuple[float, float]:
        """Calculate confidence interval
        
        Args:
            values: List of numeric values
            confidence: Confidence level (0.95 for 95%, 0.99 for 99%)
            method: 'auto', 't-dist', or 'bootstrap'
            
        Returns:
            Tuple of (lower_bound, upper_bound)
        """
        n = len(values)
        if n < 2:
            mean_val = values[0] if values else 0
            return (mean_val, mean_val)
        
        if method == 'auto':
            # Use t-distribution for small samples, bootstrap for large
            method = 't-dist' if n < 30 else 'bootstrap'
        
        if method == 't-dist':
            return AdvancedStatistics._t_confidence_interval(values, confidence)
        elif method == 'bootstrap':
            return AdvancedStatistics._bootstrap_confidence_interval(values, confidence)
        else:
            raise ValueError(f"Unknown CI method: {method}")
    
    @staticmethod
    def _t_confidence_interval(values: List[float], confidence: float) -> Tuple[float, float]:
        """Calculate CI using t-distribution (for small samples)"""
        n = len(values)
        mean = statistics.mean(values)
        std_err = statistics.stdev(values) / math.sqrt(n)
        
        df = n - 1
        t_crit = AdvancedStatistics._t_critical(df, confidence)
        
        margin = t_crit * std_err
        return (mean - margin, mean + margin)
    
    @staticmethod
    def _t_critical(df: int, confidence: float) -> float:
        """Get t-critical value for given degrees of freedom and confidence level
        
        Approximations for common confidence levels.
        For production with scipy: scipy.stats.t.ppf((1 + confidence) / 2, df)
        """
        alpha = (1 - confidence) / 2
        
        # T-critical value lookup table (two-tailed)
        if confidence >= 0.98:  # 99% CI
            if df >= 30:
                return 2.750
            elif df >= 20:
                return 2.845
            elif df >= 15:
                return 2.947
            elif df >= 10:
                return 3.169
            elif df >= 5:
                return 4.032
            else:
                return 5.841
        elif confidence >= 0.94:  # 95% CI
            if df >= 30:
                return 2.042
            elif df >= 20:
                return 2.086
            elif df >= 15:
                return 2.131
            elif df >= 10:
                return 2.228
            elif df >= 5:
                return 2.571
            else:
                return 4.303
        elif confidence >= 0.89:  # 90% CI
            if df >= 30:
                return 1.697
            elif df >= 20:
                return 1.725
            elif df >= 15:
                return 1.753
            elif df >= 10:
                return 1.812
            elif df >= 5:
                return 2.015
            else:
                return 2.920
        else:
            # Fallback to z-score
            return 1.96
    
    @staticmethod
    def _bootstrap_confidence_interval(values: List[float], confidence: float,
                                      n_bootstrap: int = 10000) -> Tuple[float, float]:
        """Calculate CI using bootstrap resampling
        
        Args:
            values: Original sample
            confidence: Confidence level
            n_bootstrap: Number of bootstrap samples
            
        Returns:
            Confidence interval bounds
        """
        means = []
        n = len(values)
        
        random.seed(42)  # Reproducible results
        for _ in range(n_bootstrap):
            sample = random.choices(values, k=n)
            means.append(statistics.mean(sample))
        
        means_sorted = sorted(means)
        alpha = 1 - confidence
        lower_idx = int(n_bootstrap * (alpha / 2))
        upper_idx = int(n_bootstrap * (1 - alpha / 2))
        
        return (means_sorted[lower_idx], means_sorted[upper_idx])
    
    @staticmethod
    def detect_outliers(values: List[float], method: str = 'iqr',
                       iqr_factor: float = 1.5, zscore_threshold: float = 3.0) -> Dict[str, Any]:
        """Detect outliers using IQR or Z-score method
        
        Args:
            values: List of numeric values
            method: 'iqr' (Interquartile Range) or 'zscore'
            iqr_factor: IQR multiplier (1.5 standard, 3.0 for extreme outliers)
            zscore_threshold: Z-score threshold (3.0 standard, 2.0 for moderate)
            
        Returns:
            Dictionary with outliers, indices, clean values, and method info
        """
        if method == 'iqr':
            return AdvancedStatistics._detect_outliers_iqr(values, iqr_factor)
        elif method == 'zscore':
            return AdvancedStatistics._detect_outliers_zscore(values, zscore_threshold)
        else:
            raise ValueError(f"Unknown outlier detection method: {method}")
    
    @staticmethod
    def _detect_outliers_iqr(values: List[float], factor: float = 1.5) -> Dict[str, Any]:
        """Detect outliers using Interquartile Range (IQR) method
        
        The IQR method identifies outliers as values that fall outside:
        [Q1 - factor*IQR, Q3 + factor*IQR]
        
        Standard factor = 1.5 (moderate outliers)
        Extreme factor = 3.0 (extreme outliers only)
        """
        if len(values) < 4:
            return {
                'outliers': [],
                'indices': [],
                'clean_values': values[:],
                'method': 'iqr',
                'message': 'Insufficient data for IQR method (need >= 4 values)'
            }
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        
        # Calculate quartiles
        q1_idx = n // 4
        q3_idx = (3 * n) // 4
        q1 = sorted_values[q1_idx]
        q3 = sorted_values[q3_idx]
        iqr = q3 - q1
        
        # Calculate fences
        lower_fence = q1 - factor * iqr
        upper_fence = q3 + factor * iqr
        
        # Identify outliers
        outliers = []
        indices = []
        clean_values = []
        
        for i, val in enumerate(values):
            if val < lower_fence or val > upper_fence:
                outliers.append(val)
                indices.append(i)
            else:
                clean_values.append(val)
        
        return {
            'outliers': outliers,
            'indices': indices,
            'clean_values': clean_values,
            'method': 'iqr',
            'factor': factor,
            'lower_fence': lower_fence,
            'upper_fence': upper_fence,
            'q1': q1,
            'q3': q3,
            'iqr': iqr,
            'below_lower': sum(1 for v in values if v < lower_fence),
            'above_upper': sum(1 for v in values if v > upper_fence)
        }
    
    @staticmethod
    def _detect_outliers_zscore(values: List[float], threshold: float = 3.0) -> Dict[str, Any]:
        """Detect outliers using Z-score method
        
        The Z-score method identifies outliers as values with:
        |z-score| > threshold
        
        where z-score = (value - mean) / stddev
        
        Standard threshold = 3.0 (99.7% of normal distribution)
        Moderate threshold = 2.0 (95% of normal distribution)
        """
        if len(values) < 3:
            return {
                'outliers': [],
                'indices': [],
                'clean_values': values[:],
                'method': 'zscore',
                'message': 'Insufficient data for Z-score method (need >= 3 values)'
            }
        
        mean = statistics.mean(values)
        stddev = statistics.stdev(values)
        
        if stddev == 0:
            return {
                'outliers': [],
                'indices': [],
                'clean_values': values[:],
                'method': 'zscore',
                'message': 'Zero standard deviation (all values identical)'
            }
        
        # Calculate z-scores and identify outliers
        outliers = []
        indices = []
        clean_values = []
        z_scores = []
        
        for i, val in enumerate(values):
            z_score = (val - mean) / stddev
            z_scores.append(z_score)
            
            if abs(z_score) > threshold:
                outliers.append(val)
                indices.append(i)
            else:
                clean_values.append(val)
        
        return {
            'outliers': outliers,
            'indices': indices,
            'clean_values': clean_values,
            'method': 'zscore',
            'threshold': threshold,
            'mean': mean,
            'stddev': stddev,
            'z_scores': z_scores,
            'max_z_score': max(abs(z) for z in z_scores)
        }
    
    @staticmethod
    def analyze_distribution(values: List[float]) -> Dict[str, Any]:
        """Analyze distribution characteristics
        
        Calculates skewness, kurtosis, and performs normality testing.
        
        Skewness:
        - 0: Symmetric
        - > 0: Right-skewed (long right tail)
        - < 0: Left-skewed (long left tail)
        
        Kurtosis (excess):
        - 0: Normal (mesokurtic)
        - > 0: Heavy-tailed (leptokurtic)
        - < 0: Light-tailed (platykurtic)
        """
        n = len(values)
        if n < 3:
            return {
                'skewness': 0,
                'kurtosis': 0,
                'is_normal': True,
                'p_value': 1.0,
                'interpretation': {
                    'skewness': 'insufficient data',
                    'kurtosis': 'insufficient data'
                }
            }
        
        mean = statistics.mean(values)
        stddev = statistics.stdev(values) if n > 1 else 0
        
        if stddev == 0:
            return {
                'skewness': 0,
                'kurtosis': 0,
                'is_normal': True,
                'p_value': 1.0,
                'interpretation': {
                    'skewness': 'no variation',
                    'kurtosis': 'no variation'
                }
            }
        
        # Skewness (3rd moment / stddev^3)
        m3 = sum((x - mean) ** 3 for x in values) / n
        skewness = m3 / (stddev ** 3)
        
        # Kurtosis (4th moment / stddev^4) - 3  (excess kurtosis)
        m4 = sum((x - mean) ** 4 for x in values) / n
        kurtosis = (m4 / (stddev ** 4)) - 3
        
        # Normality test
        is_normal, p_value = AdvancedStatistics._test_normality(values, mean, stddev)
        
        return {
            'skewness': skewness,
            'kurtosis': kurtosis,
            'is_normal': is_normal,
            'p_value': p_value,
            'interpretation': {
                'skewness': AdvancedStatistics._interpret_skewness(skewness),
                'kurtosis': AdvancedStatistics._interpret_kurtosis(kurtosis)
            }
        }
    
    @staticmethod
    def _test_normality(values: List[float], mean: float, stddev: float) -> Tuple[bool, float]:
        """Simple normality test based on empirical rule
        
        For production with scipy: scipy.stats.shapiro(values)
        
        This implementation checks if the data follows the empirical rule:
        - ~68% within 1 standard deviation
        - ~95% within 2 standard deviations
        - ~99.7% within 3 standard deviations
        """
        n = len(values)
        if n < 3:
            return (True, 1.0)
        
        # Count values within 1, 2, 3 standard deviations
        within_1sd = sum(1 for x in values if abs(x - mean) <= stddev)
        within_2sd = sum(1 for x in values if abs(x - mean) <= 2 * stddev)
        within_3sd = sum(1 for x in values if abs(x - mean) <= 3 * stddev)
        
        # Calculate percentages
        pct_1sd = within_1sd / n
        pct_2sd = within_2sd / n
        pct_3sd = within_3sd / n
        
        # Compare to expected percentages for normal distribution
        # Expected: 68.27%, 95.45%, 99.73%
        deviation = (
            abs(pct_1sd - 0.6827) * 2 +
            abs(pct_2sd - 0.9545) * 1.5 +
            abs(pct_3sd - 0.9973) * 1
        )
        
        # Convert deviation to approximate p-value
        # Higher deviation = lower p-value
        p_value = max(0.001, 1.0 - deviation)
        is_normal = p_value > 0.05
        
        return (is_normal, p_value)
    
    @staticmethod
    def _interpret_skewness(skewness: float) -> str:
        """Interpret skewness value"""
        if abs(skewness) < 0.5:
            return "approximately symmetric"
        elif skewness > 0.5:
            return "positively skewed (right tail)" if skewness < 1.0 else "highly positively skewed"
        else:
            return "negatively skewed (left tail)" if skewness > -1.0 else "highly negatively skewed"
    
    @staticmethod
    def _interpret_kurtosis(kurtosis: float) -> str:
        """Interpret excess kurtosis value"""
        if abs(kurtosis) < 0.5:
            return "mesokurtic (normal-like)"
        elif kurtosis > 0.5:
            return "leptokurtic (heavy tails)" if kurtosis < 2.0 else "highly leptokurtic"
        else:
            return "platykurtic (light tails)" if kurtosis > -2.0 else "highly platykurtic"
    
    @staticmethod
    def t_test(sample1: List[float], sample2: List[float], 
              equal_var: bool = True) -> Dict[str, Any]:
        """Perform independent samples t-test
        
        Tests whether two samples have significantly different means.
        
        Args:
            sample1: First sample (e.g., baseline)
            sample2: Second sample (e.g., current)
            equal_var: Assume equal variances (True) or use Welch's t-test (False)
            
        Returns:
            Dictionary with t-statistic, p-value, and interpretation
        """
        n1, n2 = len(sample1), len(sample2)
        if n1 < 2 or n2 < 2:
            return {
                't_statistic': 0,
                'p_value': 1.0,
                'df': 0,
                'significant': False,
                'error': 'Insufficient samples (need >= 2 in each group)'
            }
        
        mean1 = statistics.mean(sample1)
        mean2 = statistics.mean(sample2)
        var1 = statistics.variance(sample1)
        var2 = statistics.variance(sample2)
        
        if equal_var:
            # Pooled t-test
            pooled_var = ((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2)
            se = math.sqrt(pooled_var * (1/n1 + 1/n2))
            df = n1 + n2 - 2
        else:
            # Welch's t-test (unequal variances)
            se = math.sqrt(var1/n1 + var2/n2)
            # Welch-Satterthwaite degrees of freedom
            df = (var1/n1 + var2/n2)**2 / ((var1/n1)**2/(n1-1) + (var2/n2)**2/(n2-1))
            df = int(df)
        
        if se == 0:
            return {
                't_statistic': 0,
                'p_value': 1.0,
                'df': df,
                'significant': False,
                'error': 'Zero standard error (no variation)'
            }
        
        # T-statistic
        t_stat = (mean1 - mean2) / se
        
        # Approximate p-value (two-tailed)
        p_value = AdvancedStatistics._t_to_p_value(abs(t_stat), df)
        
        return {
            't_statistic': t_stat,
            'p_value': p_value,
            'df': df,
            'significant': p_value < 0.05,
            'highly_significant': p_value < 0.01,
            'mean1': mean1,
            'mean2': mean2,
            'mean_diff': mean1 - mean2,
            'effect_size': AdvancedStatistics._cohens_d(sample1, sample2),
            'interpretation': AdvancedStatistics._interpret_t_test(p_value, mean1, mean2)
        }
    
    @staticmethod
    def _t_to_p_value(t: float, df: int) -> float:
        """Approximate two-tailed p-value from t-statistic
        
        For production with scipy: scipy.stats.t.sf(abs(t), df) * 2
        
        This uses lookup tables for common critical values.
        """
        # Common critical values for two-tailed test
        if df >= 30:
            if abs(t) < 1.96:
                return 0.10
            elif abs(t) < 2.042:
                return 0.05
            elif abs(t) < 2.750:
                return 0.01
            else:
                return 0.001
        elif df >= 20:
            if abs(t) < 2.086:
                return 0.05
            elif abs(t) < 2.845:
                return 0.01
            else:
                return 0.001
        elif df >= 10:
            if abs(t) < 2.228:
                return 0.05
            elif abs(t) < 3.169:
                return 0.01
            else:
                return 0.001
        else:
            if abs(t) < 2.5:
                return 0.05
            elif abs(t) < 4.0:
                return 0.01
            else:
                return 0.001
    
    @staticmethod
    def _cohens_d(sample1: List[float], sample2: List[float]) -> float:
        """Calculate Cohen's d effect size"""
        n1, n2 = len(sample1), len(sample2)
        if n1 < 2 or n2 < 2:
            return 0.0
        
        mean1 = statistics.mean(sample1)
        mean2 = statistics.mean(sample2)
        var1 = statistics.variance(sample1)
        var2 = statistics.variance(sample2)
        
        # Pooled standard deviation
        pooled_std = math.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
        
        if pooled_std == 0:
            return 0.0
        
        return (mean1 - mean2) / pooled_std
    
    @staticmethod
    def _interpret_t_test(p_value: float, mean1: float, mean2: float) -> str:
        """Interpret t-test results"""
        diff = mean1 - mean2
        
        if p_value >= 0.05:
            return "No significant difference detected"
        elif p_value >= 0.01:
            direction = "higher" if diff > 0 else "lower"
            return f"Significant difference (p < 0.05): Sample 1 is {direction}"
        else:
            direction = "higher" if diff > 0 else "lower"
            return f"Highly significant difference (p < 0.01): Sample 1 is {direction}"
    
    @staticmethod
    def mann_whitney_u(sample1: List[float], sample2: List[float]) -> Dict[str, Any]:
        """Perform Mann-Whitney U test (non-parametric alternative to t-test)
        
        Tests whether two samples come from the same distribution.
        Does not assume normal distribution.
        
        Args:
            sample1: First sample
            sample2: Second sample
            
        Returns:
            Dictionary with U-statistic and significance
        """
        n1, n2 = len(sample1), len(sample2)
        if n1 < 1 or n2 < 1:
            return {
                'u_statistic': 0,
                'significant': False,
                'error': 'Empty samples'
            }
        
        # Combine and rank all values
        combined = [(val, 1) for val in sample1] + [(val, 2) for val in sample2]
        combined_sorted = sorted(combined, key=lambda x: x[0])
        
        # Assign ranks (handle ties by averaging ranks)
        ranks = {1: [], 2: []}
        i = 0
        while i < len(combined_sorted):
            value = combined_sorted[i][0]
            
            # Find all values equal to current value (ties)
            j = i
            while j < len(combined_sorted) and combined_sorted[j][0] == value:
                j += 1
            
            # Average rank for ties
            avg_rank = (i + j + 1) / 2  # +1 because ranks start at 1
            
            # Assign average rank to all tied values
            for k in range(i, j):
                group = combined_sorted[k][1]
                ranks[group].append(avg_rank)
            
            i = j
        
        # Calculate U statistic
        r1 = sum(ranks[1])
        u1 = r1 - (n1 * (n1 + 1)) / 2
        u2 = n1 * n2 - u1
        
        u_stat = min(u1, u2)
        
        # Determine significance
        if n1 > 20 and n2 > 20:
            # Large sample approximation (normal distribution)
            mean_u = n1 * n2 / 2
            std_u = math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12)
            z = (u_stat - mean_u) / std_u if std_u > 0 else 0
            p_value = AdvancedStatistics._z_to_p_value(abs(z))
            significant = p_value < 0.05
        else:
            # Small sample - use critical value heuristic
            critical_u = min(n1, n2) * max(n1, n2) * 0.3
            significant = u_stat < critical_u
            p_value = 0.05 if significant else 0.10
        
        return {
            'u_statistic': u_stat,
            'u1': u1,
            'u2': u2,
            'p_value': p_value,
            'significant': significant,
            'n1': n1,
            'n2': n2,
            'interpretation': 'Samples differ significantly' if significant else 'No significant difference'
        }
    
    @staticmethod
    def _z_to_p_value(z: float) -> float:
        """Approximate two-tailed p-value from z-score"""
        if abs(z) < 1.645:
            return 0.10
        elif abs(z) < 1.96:
            return 0.05
        elif abs(z) < 2.576:
            return 0.01
        else:
            return 0.001
    
    @staticmethod
    def generate_histogram(values: List[float], bins: int = 10, width: int = 60) -> str:
        """Generate ASCII histogram
        
        Args:
            values: Data values
            bins: Number of histogram bins
            width: Character width of histogram
            
        Returns:
            ASCII art histogram string
        """
        if not values or bins < 1:
            return "No data to display"
        
        min_val = min(values)
        max_val = max(values)
        range_val = max_val - min_val
        
        if range_val == 0:
            return f"All values equal to {min_val}"
        
        # Create bins
        bin_width = range_val / bins
        bin_counts = [0] * bins
        
        for val in values:
            bin_idx = min(int((val - min_val) / bin_width), bins - 1)
            bin_counts[bin_idx] += 1
        
        # Find max count for scaling
        max_count = max(bin_counts)
        
        # Generate histogram
        lines = []
        lines.append("Histogram:")
        lines.append("-" * (width + 20))
        
        for i, count in enumerate(bin_counts):
            bin_start = min_val + i * bin_width
            bin_end = bin_start + bin_width
            
            # Scale bar length
            bar_length = int((count / max_count) * width) if max_count > 0 else 0
            bar = "█" * bar_length
            
            lines.append(f"{bin_start:10.2f} | {bar} {count}")
        
        lines.append("-" * (width + 20))
        return "\n".join(lines)
    
    @staticmethod
    def generate_boxplot(values: List[float], width: int = 60) -> str:
        """Generate ASCII box plot
        
        Args:
            values: Data values
            width: Character width of plot
            
        Returns:
            ASCII art box plot string
        """
        if not values:
            return "No data to display"
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        
        # Calculate quartiles
        q1 = sorted_values[n // 4]
        q2 = sorted_values[n // 2]  # Median
        q3 = sorted_values[(3 * n) // 4]
        
        min_val = min(values)
        max_val = max(values)
        
        # IQR and fences for outliers
        iqr = q3 - q1
        lower_fence = q1 - 1.5 * iqr
        upper_fence = q3 + 1.5 * iqr
        
        # Whiskers extend to most extreme non-outlier
        lower_whisker = min(v for v in values if v >= lower_fence)
        upper_whisker = max(v for v in values if v <= upper_fence)
        
        # Scale to width
        data_range = max_val - min_val
        if data_range == 0:
            return f"All values equal to {min_val}"
        
        def scale(val):
            return int(((val - min_val) / data_range) * width)
        
        # Generate plot
        lines = []
        lines.append("Box Plot:")
        lines.append("-" * (width + 20))
        
        # Build plot line
        plot = [" "] * (width + 1)
        
        # Whiskers
        for i in range(scale(lower_whisker), scale(upper_whisker) + 1):
            if i < len(plot):
                plot[i] = "-"
        
        # Box (IQR)
        for i in range(scale(q1), scale(q3) + 1):
            if i < len(plot):
                plot[i] = "█"
        
        # Median
        med_pos = scale(q2)
        if med_pos < len(plot):
            plot[med_pos] = "|"
        
        # Outliers
        outliers = [v for v in values if v < lower_fence or v > upper_fence]
        for outlier in outliers:
            pos = scale(outlier)
            if 0 <= pos < len(plot):
                plot[pos] = "●"
        
        lines.append(f"{min_val:10.2f} {''.join(plot)} {max_val:.2f}")
        lines.append(f"{'':10} Q1={q1:.2f} | Q2={q2:.2f} | Q3={q3:.2f}")
        if outliers:
            lines.append(f"{'':10} Outliers: {len(outliers)}")
        lines.append("-" * (width + 20))
        
        return "\n".join(lines)


# Standalone test
if __name__ == "__main__":
    # Example usage
    import random
    
    print("Advanced Statistics Module - Test\n")
    
    # Generate sample data
    random.seed(42)
    normal_data = [random.gauss(100, 15) for _ in range(50)]
    normal_data.append(200)  # Add an outlier
    
    print("Sample Data (n=51, one outlier):")
    print(f"Values: {min(normal_data):.2f} to {max(normal_data):.2f}\n")
    
    # Comprehensive statistics
    stats = AdvancedStatistics.calculate_comprehensive_stats(normal_data)
    
    print("Statistics:")
    print(f"  Mean: {stats['mean']:.2f} ± {stats['ci_margin']:.2f} (95% CI)")
    print(f"  Median: {stats['median']:.2f}")
    print(f"  Std Dev: {stats['stddev']:.2f}")
    print(f"  CV: {stats['coefficient_of_variation']:.2f}%")
    print(f"  Outliers: {stats['outlier_count']} ({stats['outlier_percentage']:.1f}%)")
    if stats['outlier_count'] > 0:
        print(f"  Mean (clean): {stats['mean_clean']:.2f}")
    print(f"  Skewness: {stats['skewness']:.3f} ({stats['skewness_interpretation']})")
    print(f"  Kurtosis: {stats['kurtosis']:.3f} ({stats['kurtosis_interpretation']})")
    print(f"  Normal: {stats['is_normal']} (p={stats['normality_p_value']:.3f})")
    
    print("\n" + AdvancedStatistics.generate_histogram(normal_data, bins=10))
    print("\n" + AdvancedStatistics.generate_boxplot(normal_data))
