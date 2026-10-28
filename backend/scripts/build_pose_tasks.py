"""Reproducible packaging of source-verified models; no training or tensor changes."""
from pathlib import Path
import zipfile,hashlib
import flatbuffers
from mediapipe.tasks.metadata import schema_py_generated as tflite,metadata_schema_py_generated as meta
import argparse,io,urllib.request,tempfile,os
parser=argparse.ArgumentParser(description='Build audited Tasks bundles; normalization metadata only, unchanged neural tensor buffers')
parser.add_argument('--output',required=True)
args=parser.parse_args()
out=Path(args.output)
out.mkdir(parents=True,exist_ok=True)
SOURCE_URL='https://files.pythonhosted.org/packages/9f/99/5da7ae7f7e25847383bc2fe5a9adc7ce150dd371682f486c0666b407cad7/mediapipe-0.10.21-cp312-cp312-manylinux_2_28_x86_64.whl'
SOURCE_SIZE=35627340
SOURCE_SHA256='956eb1ebc275c629e61b085b2cab89c3a5b9e93bad1bb107348d98dafb5a4bb5'
with urllib.request.urlopen(SOURCE_URL,timeout=60) as response:
    wheel=response.read(SOURCE_SIZE+1)
if len(wheel)!=SOURCE_SIZE or hashlib.sha256(wheel).hexdigest()!=SOURCE_SHA256:
    raise ValueError('unapproved source wheel')
EXPECTED={'pose_full.task':(9398078,'c1492ead320c87471d9ae324ee00d1e057636522e991d339ff8f07e90982d4aa'),
          'hand_full.task':(7819594,'e5fe265a93d7f530428a4b22f230598c3655de527c12deed889514bc890d0508')}


def normalized(data,mean,std):
 original=tflite.ModelT.InitFromObj(tflite.Model.GetRootAsModel(data,0))
 metadata=meta.ModelMetadataT();metadata.name='Camera Monitoring source-verified bundled model'
 sub=meta.SubGraphMetadataT();tensor=meta.TensorMetadataT();tensor.name='image'
 norm=meta.NormalizationOptionsT();norm.mean=[mean];norm.std=[std]
 unit=meta.ProcessUnitT();unit.optionsType=meta.ProcessUnitOptions.NormalizationOptions;unit.options=norm
 tensor.processUnits=[unit]
 content=meta.ContentT();content.contentPropertiesType=meta.ContentProperties.ImageProperties
 props=meta.ImagePropertiesT();props.colorSpace=meta.ColorSpaceType.RGB;content.contentProperties=props;tensor.content=content
 sub.inputTensorMetadata=[tensor];sub.outputTensorMetadata=[]
 for index in original.subgraphs[0].outputs:
  t=meta.TensorMetadataT();t.name=original.subgraphs[0].tensors[index].name;sub.outputTensorMetadata.append(t)
 metadata.subgraphMetadata=[sub]
 b=flatbuffers.Builder(1024);b.Finish(metadata.Pack(b),file_identifier=b'M001')
 buffer=tflite.BufferT();buffer.data=bytearray(b.Output())
 md=tflite.MetadataT();md.name='TFLITE_METADATA';md.buffer=len(original.buffers)
 if original.metadata is None:original.metadata=[]
 original.metadata=[m for m in original.metadata if m.name not in ('TFLITE_METADATA',b'TFLITE_METADATA')]
 original.metadata.append(md);original.buffers.append(buffer)
 builder=flatbuffers.Builder(len(data)+4096);builder.Finish(original.Pack(builder),file_identifier=b'TFL3')
 result=bytes(builder.Output())
 check=tflite.ModelT.InitFromObj(tflite.Model.GetRootAsModel(result,0))
 # The tensor buffers, including all weights, are identical to the source.
 for a,b in zip(original.buffers[:-1],check.buffers[:-1]):
  assert (b'' if a.data is None else bytes(a.data))==(b'' if b.data is None else bytes(b.data))
 return result

with zipfile.ZipFile(io.BytesIO(wheel)) as source:
 bundles={
 'pose_full.task':{'pose_detector.tflite':('mediapipe/modules/pose_detection/pose_detection.tflite',127.5,127.5),'pose_landmarks_detector.tflite':('mediapipe/modules/pose_landmark/pose_landmark_full.tflite',0.,255.)},
 'hand_full.task':{'hand_detector.tflite':('mediapipe/modules/palm_detection/palm_detection_full.tflite',0.,255.),'hand_landmarks_detector.tflite':('mediapipe/modules/hand_landmark/hand_landmark_full.tflite',0.,255.)}}
 for name,entries in bundles.items():
  buffer=io.BytesIO()
  with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_STORED) as target:
   for key,(path,mean,std) in entries.items():
    b=normalized(source.read(path),mean,std)
    info=zipfile.ZipInfo(key,date_time=(1980,1,1,0,0,0));info.external_attr=0o644<<16
    target.writestr(info,b)
  data=buffer.getvalue();size,digest=EXPECTED[name]
  if len(data)!=size or hashlib.sha256(data).hexdigest()!=digest:raise ValueError('derived bundle mismatch')
  path=out/name
  if path.exists():
   if path.read_bytes()!=data:raise ValueError('refusing to overwrite an existing invalid model')
  else:
   with tempfile.NamedTemporaryFile(dir=out,delete=False) as temporary:
    temporary.write(data);filename=Path(temporary.name)
   try:os.link(filename,path)
   finally:filename.unlink(missing_ok=True)
  print('Verified derived bundle',name,digest)
