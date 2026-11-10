// ---------------------------------------------------------------
// Shared contract values from the master plan (Section 9).
// ---------------------------------------------------------------

// Body systems shown in the Layers panel.
// color: tint applied to every mesh of that system (null = keep the model's own colour).
export const SYSTEMS = [
  { id: 'integumentary', label: 'Skin (Integumentary)', color: '#d9a38b', on: false, opacity: 0.35 },
  { id: 'skeletal',      label: 'Skeletal',             color: '#ece5d3', on: true,  opacity: 1 },
  { id: 'muscular',      label: 'Muscular',             color: '#a3302b', on: false, opacity: 1 },
  { id: 'nervous',       label: 'Nervous',              color: '#e8c547', on: true,  opacity: 1 },
  { id: 'cardiovascular',label: 'Cardiovascular',       color: null,      on: true,  opacity: 1 },
  { id: 'respiratory',   label: 'Respiratory',          color: null,      on: true,  opacity: 1 },
  { id: 'digestive',     label: 'Digestive',            color: null,      on: true,  opacity: 1 },
  { id: 'urinary',       label: 'Urinary',              color: null,      on: true,  opacity: 1 },
  { id: 'endocrine',     label: 'Endocrine',            color: null,      on: true,  opacity: 1 },
  { id: 'lymphatic',     label: 'Lymphatic / Immune',   color: null,      on: true,  opacity: 1 },
  { id: 'reproductive',  label: 'Reproductive',         color: null,      on: true,  opacity: 1 },
  { id: 'other',         label: 'Other structures',     color: null,      on: true,  opacity: 1 },
];

// Keywords used to guess a system from a GLB file name or a parent node name.
export const SYSTEM_KEYWORDS = {
  integumentary: ['skin', 'integument'],
  skeletal: ['skelet', 'bone', 'osteo', 'joint', 'ligament', 'cartilage', 'femur', 'tibia', 'fibula', 'humerus', 'radius', 'ulna', 'vertebra', ' rib', 'skull', 'cranium', 'mandible', 'pelvi', 'scapula', 'clavicle', 'sternum', 'patella', 'carpal', 'tarsal', 'phalan', 'sacrum', 'coccyx', 'hip bone'],
  muscular: ['muscle', 'muscular', 'myolog'],
  nervous: ['nerv', 'neuro', 'brain', 'ventric', 'spinal cord'],
  cardiovascular: ['cardio', 'vascul', 'arter', 'vein', 'heart', 'angio'],
  respiratory: ['respir', 'lung', 'pulmo'],
  digestive: ['digest', 'splanchn', 'gastro', 'alimentary', 'gall', 'oesophag', 'esophag', 'appendix'],
  urinary: ['urin', 'kidney'],
  endocrine: ['endocrin'],
  lymphatic: ['lymph', 'immun'],
  reproductive: ['reproduct', 'genital'],
};

// The 12 shared organ ids. kw = words in a mesh name that mean "this mesh is part of that organ".
// Order matters: the first match wins.
export const ORGANS = [
  { id: 'brain', label: 'Brain', system: 'nervous',
    kw: ['brain', 'cerebr', 'cerebell', 'pons', 'medulla oblongata', 'midbrain', 'thalamus', 'hippocamp'] },
  { id: 'stomach', label: 'Stomach', system: 'digestive', kw: ['stomach'] },
  { id: 'lungs', label: 'Lungs', system: 'respiratory', kw: ['lung'] },
  { id: 'heart', label: 'Heart', system: 'cardiovascular',
    kw: ['heart', 'left ventricle', 'right ventricle', 'left atrium', 'right atrium', 'myocard'] },
  { id: 'liver', label: 'Liver', system: 'digestive', kw: ['liver'] },
  { id: 'intestines', label: 'Intestines', system: 'digestive',
    kw: ['intestin', 'colon', 'jejunum', 'ileum', 'duodenum', 'caecum', 'cecum', 'rectum'] },
  { id: 'kidneys', label: 'Kidneys', system: 'urinary', kw: ['kidney'] },
  { id: 'bladder', label: 'Bladder', system: 'urinary', kw: ['urinary bladder', 'bladder'], not: ['gall'] },
  { id: 'pancreas', label: 'Pancreas', system: 'digestive', kw: ['pancrea'] },
  { id: 'spleen', label: 'Spleen', system: 'lymphatic', kw: ['spleen'] },
  { id: 'thyroid', label: 'Thyroid', system: 'endocrine', kw: ['thyroid gland', 'lobe of thyroid'] },
  { id: 'reproductive', label: 'Reproductive organs', system: 'reproductive',
    kw: ['uterus', 'ovary', 'prostate', 'testis', 'testicle', 'uterine tube', 'epididym', 'seminal vesicle'] },
];

// Mesh names containing these words are never treated as an organ (e.g. "Hepatic artery").
export const NOT_ORGAN = ['artery', 'arteries', 'vein', 'nerve', 'ligament', 'muscle', 'lymph node'];

export const ORGAN_INFO = {
  brain: 'Controls thought, movement and the body\'s automatic functions.',
  heart: 'Pumps blood through the lungs and the rest of the body.',
  lungs: 'Exchange oxygen and carbon dioxide between air and blood.',
  liver: 'Filters blood, stores energy and makes bile and proteins.',
  stomach: 'Stores food and starts protein digestion with acid and enzymes.',
  intestines: 'Absorb nutrients (small intestine) and water (large intestine).',
  kidneys: 'Filter blood to make urine and balance fluids and salts.',
  bladder: 'Stores urine until it is passed.',
  pancreas: 'Makes digestive enzymes and the hormones insulin and glucagon.',
  spleen: 'Filters blood and helps the immune system fight infection.',
  thyroid: 'Makes hormones that set the body\'s metabolic rate.',
  reproductive: 'Produce sex cells and sex hormones.',
};

export const CREDITS = [
  { name: 'Z-Anatomy', what: '3D anatomy models', licence: 'CC BY-SA 4.0', url: 'https://www.z-anatomy.com' },
  { name: 'BodyParts3D (DBCLS)', what: 'Base anatomy data used by Z-Anatomy', licence: 'CC BY-SA 2.1 JP', url: 'https://lifesciencedb.jp/bp3d/' },
  { name: 'three.js', what: '3D engine', licence: 'MIT', url: 'https://threejs.org' },
  { name: 'React Three Fiber and drei', what: 'React renderer and helpers', licence: 'MIT', url: 'https://github.com/pmndrs' },
];

// Backend base URL. Put VITE_API_BASE=http://... in a .env file to change it.
export const API_BASE = (import.meta.env?.VITE_API_BASE) || 'http://localhost:8000';
