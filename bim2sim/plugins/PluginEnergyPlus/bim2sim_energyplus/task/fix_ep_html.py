from pathlib import Path
import json
from bs4 import BeautifulSoup
from bim2sim.tasks.base import ITask

class FixEPHtml(ITask):
    """After EP runs, post-process the HTML to move the TOC and replace GUIDs."""
    reads = ('sim_results_path',)
    touches = ('sim_results_path',)

    def run(self, sim_results_path: Path):
        report_dir = sim_results_path / self.prj_name
        zone_dict_path = report_dir / 'zone_dict.json'
        zone_map = {k.upper(): v for k, v in json.loads(zone_dict_path.read_text()).items()}

        # 1) find the HTML that contains our table
        html_path = None
        for f in report_dir.glob("*.htm"):
            if "People Internal Gains Nominal" in f.read_text():
                html_path = f
                break
        if html_path is None:
            raise FileNotFoundError(f"No HTML contains the target table in {report_dir}")

        soup = BeautifulSoup(html_path.read_text(), 'html.parser')

        # 2) Move the second TOC up
        tocs = soup.find_all('a', href="#toc")
        if len(tocs) >= 2:
            first_p = tocs[0].find_parent('p')
            second_p = tocs[1].find_parent('p')
            second_p.decompose()
            first_p.extract()
            soup.body.insert(1, first_p)

        # 3) Replace GUIDs in the Zone Name column
        header = soup.find('b', string="People Internal Gains Nominal")
        tbl = header.find_next('table')
        # find the column index
        first_row = tbl.find('tr')
        idx = None
        for i, cell in enumerate(first_row.find_all(['td','th'])):
            if "Zone Name" in cell.get_text(strip=True):
                idx = i
                break

        if idx is not None:
            for tr in tbl.find_all('tr')[1:]:
                cols = tr.find_all('td')
                if len(cols) > idx:
                    guid = cols[idx].get_text(strip=True).upper()
                    if guid in zone_map:
                        cols[idx].string.replace_with(zone_map[guid])

        # 4) write out
        out = report_dir / f"{html_path.stem}_with_names{html_path.suffix}"
        out.write_text(str(soup))
        self.logger.info(f"Wrote updated HTML: {out}")
        return sim_results_path,
