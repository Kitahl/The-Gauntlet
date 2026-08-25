#!/usr/bin/env python3
"""CI entrypoint correcting one unavailable BBEH family path in the frozen source."""
import build_package as package

package.BBEH_FAMILIES = [
    "bbeh_boolean_expressions",
    "bbeh_causal_understanding",
    "bbeh_disambiguation_qa",
    "bbeh_dyck_languages",
    "bbeh_multistep_arithmetic",
    "bbeh_object_properties",
    "bbeh_shuffled_objects",
    "bbeh_movie_recommendation",
    "bbeh_time_arithmetic",
    "bbeh_web_of_lies",
]
package.main()
