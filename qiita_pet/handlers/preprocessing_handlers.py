from tornado.web import authenticated

from .base_handlers import BaseHandler
from qiita_ware.dispatchable import preprocessor
from qiita_db.data import RawData
from qiita_db.parameters import (PreprocessedIlluminaParams,
                                 Preprocessed454Params)
from qiita_db.metadata_template import PrepTemplate
from qiita_ware.context import submit


class PreprocessHandler(BaseHandler):
    @authenticated
    def post(self):
        study_id = int(self.get_argument('study_id'))
        prep_template_id = int(self.get_argument('prep_template_id'))
        raw_data = RawData(PrepTemplate(prep_template_id).raw_data)
        param_id = int(self.get_argument('preprocessing_parameters_id'))

        # Get the preprocessing parameters
        if raw_data.filetype == 'FASTQ':
            param_constructor = PreprocessedIlluminaParams
        elif raw_data.filetype in ('FASTA', 'SFF'):
            param_constructor = Preprocessed454Params
        else:
            raise ValueError('Unknown filetype')

        job_id = submit(self.current_user.id, preprocessor, study_id,
                        prep_template_id, param_id, param_constructor)

        self.render('compute_wait.html',
                    job_id=job_id, title='Preprocessing',
                    completion_redirect='/study/description/%d?top_tab='
                                        'raw_data_tab&sub_tab=%s&prep_tab=%s'
                                        % (study_id, raw_data.id,
                                           prep_template_id))
