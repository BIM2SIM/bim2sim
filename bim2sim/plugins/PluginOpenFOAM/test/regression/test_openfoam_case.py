import os
import sys
import filecmp
import difflib
import unittest
import logging
from pathlib import Path

import bim2sim
from bim2sim.utilities.types import LOD, IFCDomain
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.utilities.test import RegressionTestBase

logger = logging.getLogger(__name__)


class RegressionTestOpenFOAM(RegressionTestBase):
    """Class to set up and run CFD regression tests."""

    def setUp(self):
        self.old_stderr = sys.stderr
        self.working_dir = os.getcwd()
        self.ref_results_src_path = None
        self.results_src_dir = None
        self.results_dst_dir = None
        self.tester = None
        super().setUp()

    def tearDown(self):
        os.chdir(self.working_dir)
        sys.stderr = self.old_stderr
        super().tearDown()

    @staticmethod
    def generate_html_diff_report(new_dir: Path, ref_dir: Path,
                                  output_html: str,
                                  context_lines: int = 5):
        """
        Recursively compare reference vs generated directories and produce an HTML report.
        Returns a tuple (has_diffs: bool, html_path: str).
        """
        html_sections = []
        diffs_found = False

        differ = difflib.HtmlDiff(tabsize=4, wrapcolumn=80)
        for root, _, files in os.walk(ref_dir):
            rel_root = os.path.relpath(root, ref_dir)
            gen_root = new_dir / rel_root

            if not gen_root.exists():
                html_sections.append(
                    f"<h3>Missing directory in generated: {rel_root}</h3>")
                diffs_found = True
                continue

            for f in files:
                ref_file = Path(root) / f
                gen_file = gen_root / f
                if not gen_file.exists():
                    diffs_found = True
                    html_sections.append(
                        f"<h4>Missing file in generated: "
                        f"{os.path.join(rel_root, f)}</h4>"
                    )
                    continue
                if filecmp.cmp(ref_file, gen_file, shallow=False):
                    continue  # identical, skip
                diffs_found = True
                with open(ref_file, "r", encoding="utf-8",
                          errors="replace") as rf:
                    ref_lines = rf.read().splitlines()
                with open(gen_file, "r", encoding="utf-8",
                          errors="replace") as gf:
                    gen_lines = gf.read().splitlines()

                desc_from = f"Reference: {os.path.join(rel_root, f)}"
                desc_to = f"Generated: {os.path.join(rel_root, f)}"
                table_html = differ.make_table(ref_lines, gen_lines,
                                               fromdesc=desc_from,
                                               todesc=desc_to,
                                               context=True,
                                               numlines=context_lines)
                html_sections.append(
                    f"<h2>{os.path.join(rel_root, f)}</h2>\n{table_html}")

        # Check for unexpected extra files in generated_dir
        extra_files = []
        for root, _, files in os.walk(new_dir):
            rel_root = os.path.relpath(root, new_dir)
            for f in files:
                gen_path = Path(root) / f
                ref_path = ref_dir / rel_root / f
                if not ref_path.exists():
                    extra_files.append(os.path.join(rel_root, f))
                    print(
                        f"Extra file in generated: "
                        f"{os.path.join(rel_root, f)}")  # progress print, todo

        if extra_files:
            diffs_found = True
            extras_html = \
                "<h3>Unexpected extra files in generated:</h3>\n<ul>\n"
            for ef in extra_files:
                extras_html += f"<li>{ef}</li>\n"
            extras_html += "</ul>\n"
            html_sections.insert(0, extras_html)  # show extras near top

        # Build full HTML page
        html_body = "\n<hr/>\n".join(
            html_sections) if html_sections else "<p>No differences found.</p>"
        html_page = f"""<!doctype html>
        <html lang="en">
        <head>
        <meta charset="utf-8">
        <title>Regression Test Diff Report</title>
        <style>
          body {{ font-family: Arial, sans-serif; padding: 1rem; }}
          h1 {{ margin-bottom: .5rem; }}
          table.diff {{ width: 100%; border-collapse: collapse; }}
          table.diff td, table.diff th {{ padding: 4px; vertical-align: top; font-family: monospace; }}
          /* difflib default classes: diff_header, diff_next, diff_add, diff_chg, diff_sub */
          .diff_add {{ background-color: #99ffb6; }}   /* added in generated */
          .diff_chg {{ background-color: #ffe74d; }}   /* changed */
          .diff_sub {{ background-color: #ff808e; }}   /* removed from reference */
          .diff_header {{ background-color: #f0f0f0; font-weight: bold; }}
          .center {{ text-align:center; }}
        </style>
        </head>
        <body>
        <h1>Regression Test Diff Report</h1>
        <p><b>Reference dir:</b> {ref_dir}</p>
        <p><b>Generated dir:</b> {new_dir}</p>
        <hr/>
        {html_body}
        </body>
        </html>
        """
        # Ensure parent exists
        out_path = Path(output_html)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html_page, encoding="utf-8")
        print(f"HTML diff report written to: {out_path}")
        return diffs_found, str(out_path)

    def create_regression_setup(self):
        passed_regression_test = True
        ref_results_dir = Path(bim2sim.__file__).parent.parent \
            / "test/resources/arch/regression_results" \
            / self.project.name / 'OpenFOAM'
        sim_output_dir = self.project.paths.export / "OpenFOAM"
        regression_results_dir = (self.project.paths.root /
                                  "regression_results" / "cfd" /
                                  self.project.name / "OpenFOAM")
        regression_results_dir.mkdir(parents=True, exist_ok=True)
        html_report_path = regression_results_dir / "diff_report.html"
        print(f"Generating HTML diff report: {html_report_path}")
        has_diffs, report_path = self.generate_html_diff_report(sim_output_dir,
                                                           ref_results_dir,
                                                           html_report_path)
        if has_diffs:
            passed_regression_test = False
            logger.error(
                f"Regression test failed. Results are written to {report_path}.")
        return passed_regression_test

    def run_regression_test(self):
        return self.create_regression_setup()


class TestRegressionOpenFOAMCase(RegressionTestOpenFOAM, unittest.TestCase):
    """Regression tests for PluginOpenFOAM."""
    def test_regression_AC20_FZK_Haus(self):
        """Run PluginOpenFOAM regression test with AC20-FZK-Haus.ifc."""
        ifc_path = {IFCDomain.arch: 'AC20-FZK-Haus.ifc'}
        project = self.create_project(ifc_path, "openfoam")

        project.sim_settings.weather_file_path = \
            (self.test_resources_path() /
             'weather_files/DEU_NW_Aachen.105010_TMYx.epw')
        project.sim_settings.cfd_export = True
        project.sim_settings.select_space_guid = '2RSCzLOBz4FAK$_wE8VckM'
        project.sim_settings.simulation_time = 12
        project.sim_settings.simulation_date = "01/14"
        project.sim_settings.add_heating = True
        project.sim_settings.heater_radiation = 0.6
        project.sim_settings.radiation_model = 'P1'
        project.sim_settings.add_airterminals = True
        project.sim_settings.inlet_type = 'SimpleStlDiffusor'
        project.sim_settings.outlet_type = 'SimpleStlDiffusor'
        project.sim_settings.mesh_size = 0.15
        project.sim_settings.cluster_max_runtime_simulation = "02:59:00"
        project.sim_settings.cluster_max_runtime_meshing = "00:20:00"
        project.sim_settings.cluster_jobname = "RegressionTest"
        project.sim_settings.cluster_compute_account = "test1234"
        project.sim_settings.cluster_cpu_per_node = 48
        project.sim_settings.n_procs = 72
        project.sim_settings.total_iterations = 5000

        handler = DebugDecisionHandler(())
        handler.handle(project.run())

        reg_test_res = self.run_regression_test()
        self.assertTrue(reg_test_res,
                        "OpenFOAM Regression test did not finish successfully "
                        "or created deviations.")

    def test_regression_DigitalHub_SB89(self):
        """Run PluginOpenFOAM regression test with DigitalHub."""
        ifc_paths = {
            IFCDomain.arch:
                Path(bim2sim.__file__).parent.parent /
                'test/resources/arch/ifc/FM_ARC_DigitalHub_with_SB89.ifc',
            IFCDomain.ventilation:
                Path(bim2sim.__file__).parent.parent /
                'test/resources/hydraulic/ifc/DigitalHub_Gebaeudetechnik'
                '-LUEFTUNG_v2.ifc',
            IFCDomain.hydraulic:
                Path(bim2sim.__file__).parent.parent /
                'test/resources/hydraulic/ifc/DigitalHub_Gebaeudetechnik-HEIZUNG_v2'
                '.ifc',
        }
        project = self.create_project(ifc_paths, "openfoam")

        project.sim_settings.weather_file_path = \
            (self.test_resources_path() /
             'weather_files/DEU_NW_Aachen.105010_TMYx.epw')
        project.sim_settings.prj_custom_usages = (Path(
            bim2sim.__file__).parent.parent / "test/resources/arch/custom_usages/"
            "customUsagesFM_ARC_DigitalHub_with_SB89.json")
        project.sim_settings.cfd_export = True
        project.sim_settings.select_space_guid = '3hiy47ppf5B8MyZqbpTfpc'
        project.sim_settings.inlet_type = 'Original'
        project.sim_settings.outlet_type = 'Original'
        project.sim_settings.add_heating = True
        project.sim_settings.add_people = True
        project.sim_settings.add_floorheating = False
        project.sim_settings.add_airterminals = True
        project.sim_settings.add_comfort = True
        project.sim_settings.add_furniture = True
        project.sim_settings.add_people = True
        project.sim_settings.add_comfort = True
        project.sim_settings.furniture_setting = 'Office'
        project.sim_settings.furniture_amount = 8
        project.sim_settings.people_amount = 4
        project.sim_settings.people_setting = 'Seated'
        project.sim_settings.radiation_precondition_time = 4000
        project.sim_settings.radiation_model = 'preconditioned_fvDOM'
        project.sim_settings.output_keys = ['output_outdoor_conditions',
                                            'output_zone_temperature',
                                            'output_zone',
                                            'output_infiltration',
                                            'output_meters',
                                            'output_internal_gains']

        answers = ('Autodesk Revit', 'Autodesk Revit', *(None,) * 13,
                   *('HVAC-AirTerminal',) * 3, *(None,) * 2, 2015)
        handler = DebugDecisionHandler(answers)
        handler.handle(project.run())

        reg_test_res = self.run_regression_test()
        self.assertTrue(reg_test_res,
                        "OpenFOAM Regression test did not finish successfully "
                        "or created deviations.")
